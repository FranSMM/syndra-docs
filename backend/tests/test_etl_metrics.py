"""
Unit tests for the ETL collectors (app/core/metrics.py), which derive pipeline
stage durations from Prefect's own database instead of counting them in process.

Same approach as test_domain_metrics.py: the session factory is stubbed, so the
statements are built but never executed. That covers the translation from rows
to gauge samples, but deliberately not the SQL itself: these statements are
raw text() against tables Syndra does not own, so nothing here would notice a
typo in them. The statements are checked against the real schema separately,
before deploying.
"""
from types import SimpleNamespace

import pytest
from prometheus_client import REGISTRY

from app.core import metrics

pytestmark = pytest.mark.asyncio


def stage_row(stage, runs=1, avg=1.0, p95=2.0):
    return SimpleNamespace(stage=stage, runs=runs, avg_seconds=avg, p95_seconds=p95)


def flow_row(state, total=1):
    return SimpleNamespace(state=state, total=total)


class _StubResult:
    def __init__(self, payload):
        self._payload = payload

    def all(self):
        return self._payload

    def scalar(self):
        return self._payload


class _StubSession:
    """
    Answers execute() with the queued payloads in order: stages, flow states,
    then the scalar last-run timestamp, which is the exact order _read_etl
    issues them in.
    """

    def __init__(self, payloads):
        self._pending = list(payloads)
        self.executed = 0

    async def execute(self, statement):
        self.executed += 1
        return _StubResult(self._pending.pop(0))


class _StubFactory:
    def __init__(self, stage_rows, flow_rows, last_run_epoch=1_788_000_000.0):
        self.session = _StubSession([stage_rows, flow_rows, last_run_epoch])

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc_info):
        return False


def sample(name, labels=None):
    return REGISTRY.get_sample_value(name, labels or {})


async def test_stage_durations_are_published_per_statistic():
    factory = _StubFactory(
        [
            stage_row("MLOps: Vector Indexing", runs=24, avg=8.59, p95=9.02),
            stage_row("Load: PostgreSQL async", runs=24, avg=0.88, p95=2.16),
        ],
        [flow_row("COMPLETED", 24)],
    )

    await metrics.refresh_etl_metrics(factory, force=True)

    assert sample(
        "syndra_etl_stage_duration_seconds",
        {"stage": "MLOps: Vector Indexing", "stat": "avg"},
    ) == 8.59
    assert sample(
        "syndra_etl_stage_duration_seconds",
        {"stage": "MLOps: Vector Indexing", "stat": "p95"},
    ) == 9.02
    assert sample("syndra_etl_stage_runs", {"stage": "Load: PostgreSQL async"}) == 24


async def test_flow_states_and_last_run_are_published():
    factory = _StubFactory(
        [stage_row("Extract: Generic RSS Spiders")],
        [flow_row("COMPLETED", 23), flow_row("FAILED", 1)],
        last_run_epoch=1_788_800_000.0,
    )

    await metrics.refresh_etl_metrics(factory, force=True)

    assert sample("syndra_etl_flow_runs", {"state": "COMPLETED"}) == 23
    assert sample("syndra_etl_flow_runs", {"state": "FAILED"}) == 1
    assert sample("syndra_etl_last_flow_run_timestamp_seconds") == 1_788_800_000.0


async def test_a_stage_that_stops_running_loses_its_labels():
    """
    Same reasoning as the source gauges: a stage removed from the flow would
    otherwise keep reporting its final duration for as long as the process
    lives, and a frozen series looks alive.
    """
    first = _StubFactory([stage_row("Retired: Old Spider", runs=3)], [flow_row("COMPLETED", 3)])
    await metrics.refresh_etl_metrics(first, force=True)
    assert sample("syndra_etl_stage_runs", {"stage": "Retired: Old Spider"}) == 3

    second = _StubFactory([stage_row("Load: PostgreSQL async", runs=9)], [flow_row("COMPLETED", 9)])
    await metrics.refresh_etl_metrics(second, force=True)

    assert sample("syndra_etl_stage_runs", {"stage": "Retired: Old Spider"}) is None
    assert sample(
        "syndra_etl_stage_duration_seconds",
        {"stage": "Retired: Old Spider", "stat": "avg"},
    ) is None


async def test_a_stage_with_no_duration_reports_runs_but_no_seconds():
    factory = _StubFactory(
        [stage_row("Odd: No Duration", runs=2, avg=None, p95=None)],
        [flow_row("COMPLETED", 2)],
    )

    await metrics.refresh_etl_metrics(factory, force=True)

    assert sample("syndra_etl_stage_runs", {"stage": "Odd: No Duration"}) == 2
    assert sample(
        "syndra_etl_stage_duration_seconds", {"stage": "Odd: No Duration", "stat": "avg"}
    ) is None


async def test_a_stack_that_never_ran_does_not_claim_1970():
    """
    max(start_time) is NULL on a fresh Prefect database. Setting the gauge to 0
    would place the last pipeline run at 1 January 1970 and make every freshness
    check read as catastrophically broken on a stack that is merely new.
    """
    known = _StubFactory(
        [stage_row("Load: PostgreSQL async")], [flow_row("COMPLETED", 1)],
        last_run_epoch=1_788_800_123.0,
    )
    await metrics.refresh_etl_metrics(known, force=True)

    empty = _StubFactory(
        [stage_row("Load: PostgreSQL async")], [flow_row("COMPLETED", 1)],
        last_run_epoch=None,
    )
    await metrics.refresh_etl_metrics(empty, force=True)

    assert sample("syndra_etl_last_flow_run_timestamp_seconds") == 1_788_800_123.0


async def test_second_refresh_within_the_ttl_hits_no_database():
    warm = _StubFactory([stage_row("Load: PostgreSQL async", runs=7)], [flow_row("COMPLETED", 7)])
    assert await metrics.refresh_etl_metrics(warm, force=True) is True
    assert warm.session.executed == 3

    cached = _StubFactory([stage_row("Load: PostgreSQL async", runs=999)], [flow_row("COMPLETED", 999)])
    assert await metrics.refresh_etl_metrics(cached) is False

    assert cached.session.executed == 0
    assert sample("syndra_etl_stage_runs", {"stage": "Load: PostgreSQL async"}) == 7


async def test_prefect_being_unreachable_does_not_propagate():
    """
    Prefect's database is a second, independent dependency of /metrics. It going
    down must cost its own gauges and nothing else: not the HTTP histograms,
    and not the Syndra domain gauges that live in a different database.
    """

    class _ExplodingFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            raise RuntimeError("connection refused")

        async def __aexit__(self, *exc_info):
            return False

    assert await metrics.refresh_etl_metrics(_ExplodingFactory(), force=True) is False


async def test_stage_names_are_normalised_in_sql_not_in_python():
    """
    Prefect names every task run "<stage>-<hash>", so the hash has to be
    stripped before the name becomes a label or each run creates a new series.
    That stripping happens in the query, which means no amount of stubbed rows
    can prove it is there: this asserts on the statement itself.
    """
    sql = str(metrics._etl_stage_statement())

    assert "regexp_replace" in sql
    assert metrics._STAGE_NAME_SUFFIX in sql
