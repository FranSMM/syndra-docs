"""
Unit tests for the Prometheus domain collectors (app/core/metrics.py).

Like test_deduplication.py, these need no running stack: the session factory is
stubbed, so the SQLAlchemy statements are built but never executed. What is
under test is the translation from query rows to gauge samples, plus the two
behaviours that are easy to get silently wrong: the 60s cache that keeps a
15s scrape from hammering Postgres, and the removal of labels for sources that
have stopped existing.

Gauge values are read back through the default REGISTRY rather than from the
Gauge objects, because that is what /metrics actually serves.
"""
from types import SimpleNamespace

import pytest
from prometheus_client import REGISTRY

from app.core import metrics

pytestmark = pytest.mark.asyncio


def source_row(source, total=0, with_tickers=0, age=0.0, without_date=0):
    """One row of the per-source aggregate query."""
    return SimpleNamespace(
        source=source,
        total=total,
        with_tickers=with_tickers,
        without_date=without_date,
        last_article_age_seconds=age,
    )


def state_row(state, total=0):
    """One row of the ingestion_state aggregate query."""
    return SimpleNamespace(state=state, total=total)


class _StubResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _StubSession:
    """
    Returns the queued result sets in call order: first execute() answers the
    per-source query, second the ingestion-state one. Order-coupled on purpose:
    it keeps the stub trivial, and refresh_domain_metrics runs exactly these two
    statements in exactly this order.
    """

    def __init__(self, result_sets):
        self._pending = list(result_sets)
        self.executed = 0

    async def execute(self, statement):
        self.executed += 1
        return _StubResult(self._pending.pop(0))


class _StubFactory:
    """Stands in for AsyncSessionLocal: calling it yields an async ctx manager."""

    def __init__(self, source_rows, state_rows):
        self.session = _StubSession([source_rows, state_rows])

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc_info):
        return False


def sample(name, labels=None):
    return REGISTRY.get_sample_value(name, labels or {})


async def test_source_gauges_are_set_from_query_rows():
    factory = _StubFactory(
        [
            source_row("global_finance_rss", total=1200, with_tickers=800, age=90.0),
            source_row("sec_press_releases", total=340, with_tickers=340, age=1_209_600.0),
        ],
        [state_row("processed", 1540), state_row("pending", 7)],
    )

    await metrics.refresh_domain_metrics(factory, force=True)

    assert sample("syndra_articles", {"source": "global_finance_rss"}) == 1200
    assert sample("syndra_articles", {"source": "sec_press_releases"}) == 340
    assert sample(
        "syndra_source_last_article_age_seconds", {"source": "sec_press_releases"}
    ) == 1_209_600.0
    # Global gauge, summed across sources: never labelled by ticker (10k+ series).
    assert sample("syndra_articles_with_tickers") == 1140


async def test_ingestion_states_default_to_zero_when_absent():
    """
    A state missing from the GROUP BY means zero rows in it, not "unknown". The
    failed gauge has to report 0 rather than disappear, because the whole point
    is being able to show a flat zero line for the defence.
    """
    factory = _StubFactory(
        [source_row("global_finance_rss", total=10, with_tickers=4, age=5.0)],
        [state_row("processed", 10)],
    )

    await metrics.refresh_domain_metrics(factory, force=True)

    assert sample("syndra_ingestion_pending") == 0
    assert sample("syndra_ingestion_failed") == 0


async def test_ingestion_states_are_reported_when_present():
    factory = _StubFactory(
        [source_row("global_finance_rss", total=10, with_tickers=4, age=5.0)],
        [state_row("processed", 10), state_row("pending", 3), state_row("failed", 2)],
    )

    await metrics.refresh_domain_metrics(factory, force=True)

    assert sample("syndra_ingestion_pending") == 3
    assert sample("syndra_ingestion_failed") == 2


async def test_source_that_disappears_loses_its_labels():
    """
    Gauge children persist until removed. Without an explicit clear, a source
    dropped from feeds.json would keep reporting its last value forever: a
    frozen series is worse than an absent one, because it looks alive.
    """
    first = _StubFactory(
        [source_row("retired_feed", total=5, with_tickers=1, age=10.0)],
        [state_row("processed", 5)],
    )
    await metrics.refresh_domain_metrics(first, force=True)
    assert sample("syndra_articles", {"source": "retired_feed"}) == 5

    second = _StubFactory(
        [source_row("global_finance_rss", total=9, with_tickers=2, age=20.0)],
        [state_row("processed", 9)],
    )
    await metrics.refresh_domain_metrics(second, force=True)

    assert sample("syndra_articles", {"source": "retired_feed"}) is None
    assert sample("syndra_articles", {"source": "global_finance_rss"}) == 9


async def test_articles_with_a_rejected_date_are_counted_not_hidden():
    """
    The enrichment stores NULL when a feed's date cannot be true. Those articles
    disappear from every time-window query, so without this gauge the rejection
    is a silent subtraction from the corpus.
    """
    factory = _StubFactory(
        [source_row("sec_press_releases", total=39, with_tickers=6, age=90.0, without_date=2)],
        [state_row("processed", 39)],
    )

    await metrics.refresh_domain_metrics(factory, force=True)

    assert sample(
        "syndra_articles_without_publication_date", {"source": "sec_press_releases"}
    ) == 2


async def test_source_with_no_published_date_reports_no_age():
    """
    MAX(published_at) is NULL for a source whose rows all lack a date. Emitting
    0 there would read as "perfectly fresh", which is a lie; the series is
    simply absent, and the count still gets reported.
    """
    factory = _StubFactory(
        [source_row("undated_feed", total=4, with_tickers=0, age=None)],
        [state_row("processed", 4)],
    )

    await metrics.refresh_domain_metrics(factory, force=True)

    assert sample("syndra_articles", {"source": "undated_feed"}) == 4
    assert sample("syndra_source_last_article_age_seconds", {"source": "undated_feed"}) is None


async def test_second_refresh_within_the_ttl_hits_no_database():
    """
    The cache is the whole reason a 15s scrape interval is affordable. Without
    it every scrape would run two aggregate queries against Postgres.
    """
    warm = _StubFactory(
        [source_row("global_finance_rss", total=42, with_tickers=7, age=1.0)],
        [state_row("processed", 42)],
    )
    assert await metrics.refresh_domain_metrics(warm, force=True) is True
    assert warm.session.executed == 2

    cached = _StubFactory(
        [source_row("global_finance_rss", total=999, with_tickers=999, age=999.0)],
        [state_row("processed", 999)],
    )
    assert await metrics.refresh_domain_metrics(cached) is False

    assert cached.session.executed == 0
    assert sample("syndra_articles", {"source": "global_finance_rss"}) == 42


async def test_a_failing_query_does_not_propagate():
    """
    /metrics must keep serving the HTTP metrics even when Postgres is down.
    A scrape that 500s loses the request latencies too, which are the numbers
    the Results chapter actually needs.
    """

    class _ExplodingFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            raise RuntimeError("connection refused")

        async def __aexit__(self, *exc_info):
            return False

    assert await metrics.refresh_domain_metrics(_ExplodingFactory(), force=True) is False
