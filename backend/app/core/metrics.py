"""
Prometheus domain collectors. HTTP metrics come from the instrumentator; these
are the Syndra-specific facts no library can guess.

Three rules for anyone editing this file:

1. Gauges are derived from SQL, never counted in process. In-process counters
   reset on restart and drift once the scheduler writes to Postgres. See
   ADR 038 and INC-021.
2. Never label by ticker. Three sources against 10657 tickers is the difference
   between a dashboard and an OOM.
3. No `_total` suffix. Prometheus reserves it for counters and promtool rejects
   it on gauges. Renaming later orphans the collected history.
"""
import asyncio
import logging
import time

from prometheus_client import Gauge
from sqlalchemy import and_, func, select, text

from app.db.session import AsyncSessionLocal, PrefectSessionLocal
from app.models.article import Article
from app.models.raw_article import RawArticle

logger = logging.getLogger(__name__)

# Prometheus scrapes every 15s; these queries are aggregates over the whole
# corpus. Recomputing them four times a minute buys no resolution that matters
# for numbers that move on an hourly pipeline, so the result is held for 60s and
# scrapes in between are served from the last read.
DOMAIN_METRICS_TTL_SECONDS = 60

# Ingestion states that must always be reported. A state missing from the
# GROUP BY means zero rows in it, and zero is a fact worth graphing: especially
# `failed`, where a flat zero line is the claim being made.
_TRACKED_INGESTION_STATES = ("pending", "failed")


SOURCE_LAST_ARTICLE_AGE = Gauge(
    "syndra_source_last_article_age_seconds",
    "Age of the most recent article published by each source, in seconds",
    ["source"],
)

ARTICLES = Gauge(
    "syndra_articles",
    "Enriched articles in the Silver layer, by source",
    ["source"],
)

INGESTION_PENDING = Gauge(
    "syndra_ingestion_pending",
    "Bronze articles still awaiting enrichment",
)

INGESTION_FAILED = Gauge(
    "syndra_ingestion_failed",
    "Bronze articles whose enrichment failed",
)

ARTICLES_WITH_TICKERS = Gauge(
    "syndra_articles_with_tickers",
    "Enriched articles with at least one extracted ticker",
)

# The enrichment stores NULL when a feed's date is unparseable or cannot be true
#: see app/core/dates.py. Those articles are still served by ticker queries but
# vanish from every time-window query, so without this the rejection is a silent
# subtraction from the corpus. A rising value here means a feed's dates have
# started lying, which is a data-quality signal no other metric carries.
ARTICLES_WITHOUT_DATE = Gauge(
    "syndra_articles_without_publication_date",
    "Enriched articles whose publication date was missing or rejected, by source",
    ["source"],
)

# --- ETL, derived from Prefect's database ------------------------------------
# The pipeline runs hourly, so a 24h window is roughly 24 observations per
# stage: enough for a p95 that means something, short enough that a slowdown
# shows up the same day instead of being averaged away over a week.
ETL_WINDOW_HOURS = 24

# Prefect appends a short hash to every task run name ("Load: PostgreSQL
# async-f49"), which makes each execution a distinct string. Used raw as a label
# it would create a new time series per run: the cardinality explosion, arriving
# from an unexpected direction. Stripped back to the stage name declared in
# app/pipeline.py.
_STAGE_NAME_SUFFIX = r"-[0-9a-f]+$"

ETL_STAGE_DURATION = Gauge(
    "syndra_etl_stage_duration_seconds",
    f"ETL stage duration over the last {ETL_WINDOW_HOURS}h, by statistic",
    ["stage", "stat"],
)

ETL_STAGE_RUNS = Gauge(
    "syndra_etl_stage_runs",
    f"ETL task runs recorded in the last {ETL_WINDOW_HOURS}h, by stage",
    ["stage"],
)

ETL_FLOW_RUNS = Gauge(
    "syndra_etl_flow_runs",
    f"ETL flow runs in the last {ETL_WINDOW_HOURS}h, by terminal state",
    ["state"],
)

# A timestamp rather than an age, which is the form Prometheus asks for: the
# consumer writes `time() - syndra_etl_last_flow_run_timestamp_seconds` and gets
# an answer that keeps growing even if this endpoint stops being scraped. An age
# computed here freezes at whatever it was when the process last managed to
# compute it, which reads as "recent" exactly when it is not.
#
# syndra_source_last_article_age_seconds predates that realisation and has the
# weaker form. Not changed here: a rename starts a new series and orphans what
# has already been collected. Worth revisiting when the Grafana work lands in
# October, where the cost of a rename is lowest.
ETL_LAST_FLOW_RUN = Gauge(
    "syndra_etl_last_flow_run_timestamp_seconds",
    "Unix timestamp of the most recent ETL flow run",
)

# Not in the original catalogue, added because the gauges above are the kind
# that lie by omission. If Postgres is unreachable the last read stays published
# rather than vanishing, so a frozen corpus size looks identical to a stable
# one. This timestamp is what tells the two apart.
DOMAIN_METRICS_LAST_SUCCESS = Gauge(
    "syndra_domain_metrics_last_success_timestamp_seconds",
    "Unix timestamp of the last successful refresh of the domain gauges",
)


ETL_METRICS_LAST_SUCCESS = Gauge(
    "syndra_etl_metrics_last_success_timestamp_seconds",
    "Unix timestamp of the last successful refresh of the ETL gauges",
)


class _CachedRefresh:
    """
    Runs a reader at most once per TTL, with concurrent scrapes collapsing onto
    the first caller instead of queueing identical queries behind it.

    One instance per database, not one shared cache. Prefect's database becoming
    unreachable must not stop the Syndra gauges from refreshing, and a single
    try/except wrapped around both reads would do exactly that.
    """

    def __init__(self, name: str, ttl_seconds: int, last_success_gauge: Gauge):
        self._name = name
        self._ttl = ttl_seconds
        self._last_success_gauge = last_success_gauge
        self._last_monotonic: float | None = None
        self._lock = asyncio.Lock()

    def _is_fresh(self) -> bool:
        return (
            self._last_monotonic is not None
            and time.monotonic() - self._last_monotonic < self._ttl
        )

    async def run(self, session_factory, reader, *, force: bool = False) -> bool:
        if not force and self._is_fresh():
            return False

        async with self._lock:
            # Re-checked inside the lock: concurrent scrapes queue here, and
            # without this the second would run the queries the first just ran.
            if not force and self._is_fresh():
                return False

            try:
                async with session_factory() as session:
                    await reader(session)
            except Exception as exc:
                # Deliberately broad: a scrape is not a request path, and there
                # is no caller to hand the failure to. The previous values stay
                # published and the last-success gauge stops advancing, which is
                # how a consumer notices they are stale.
                logger.warning("%s metrics refresh failed: %s", self._name, exc)
                return False

            self._last_monotonic = time.monotonic()
            self._last_success_gauge.set(time.time())
            return True


_domain_refresh = _CachedRefresh(
    "Domain", DOMAIN_METRICS_TTL_SECONDS, DOMAIN_METRICS_LAST_SUCCESS
)
_etl_refresh = _CachedRefresh("ETL", DOMAIN_METRICS_TTL_SECONDS, ETL_METRICS_LAST_SUCCESS)


def _source_stats_statement():
    """
    One pass over the Silver layer for the three per-source facts.

    The age is computed in SQL rather than in Python because published_at is a
    naive column: subtracting it from a Python datetime means guessing which
    timezone it is in. `timezone('utc', now())` gives Postgres a naive UTC
    instant to subtract, so the arithmetic happens where the data lives and
    carries no assumption about the container clock.
    """
    return (
        select(
            Article.source.label("source"),
            func.count().label("total"),
            func.count()
            .filter(
                and_(
                    Article.tickers.isnot(None),
                    func.cardinality(Article.tickers) > 0,
                )
            )
            .label("with_tickers"),
            func.count()
            .filter(Article.published_at.is_(None))
            .label("without_date"),
            func.extract(
                "epoch",
                func.timezone("utc", func.now()) - func.max(Article.published_at),
            ).label("last_article_age_seconds"),
        )
        .group_by(Article.source)
    )


def _ingestion_states_statement():
    return select(
        RawArticle.ingestion_state.label("state"),
        func.count().label("total"),
    ).group_by(RawArticle.ingestion_state)


def _publish_source_stats(rows) -> None:
    # Gauge children outlive the data behind them: a source removed from
    # feeds.json would keep reporting its final value until the process
    # restarted. Clearing first means a source that stops existing stops being
    # reported, which is the honest representation.
    ARTICLES.clear()
    SOURCE_LAST_ARTICLE_AGE.clear()
    ARTICLES_WITHOUT_DATE.clear()

    articles_with_tickers = 0
    for row in rows:
        ARTICLES.labels(source=row.source).set(row.total)
        ARTICLES_WITHOUT_DATE.labels(source=row.source).set(row.without_date or 0)
        articles_with_tickers += row.with_tickers or 0

        # NULL when every row of that source lacks a published date. Reporting
        # 0 would read as "published a moment ago"; no series at all is what
        # "unknown" actually looks like in Prometheus.
        if row.last_article_age_seconds is not None:
            SOURCE_LAST_ARTICLE_AGE.labels(source=row.source).set(
                row.last_article_age_seconds
            )

    ARTICLES_WITH_TICKERS.set(articles_with_tickers)


def _etl_stage_statement():
    """
    Duration per pipeline stage over the window, straight from Prefect's own
    task_run table.

    Raw SQL rather than the ORM on purpose: these tables belong to Prefect, not
    to Syndra. Mapping them into app/models/ would create a second, unversioned
    definition of a schema someone else migrates, and Alembic would start
    offering to "fix" tables it does not own.
    """
    return text(
        f"""
        SELECT regexp_replace(name, '{_STAGE_NAME_SUFFIX}', '') AS stage,
               count(*) AS runs,
               extract(epoch FROM avg(total_run_time)) AS avg_seconds,
               extract(epoch FROM percentile_cont(0.95)
                   WITHIN GROUP (ORDER BY total_run_time)) AS p95_seconds
        FROM task_run
        WHERE start_time > now() - interval '{ETL_WINDOW_HOURS} hours'
          AND total_run_time IS NOT NULL
        GROUP BY stage
        """
    )


def _etl_flow_states_statement():
    return text(
        f"""
        SELECT state_type AS state, count(*) AS total
        FROM flow_run
        WHERE start_time > now() - interval '{ETL_WINDOW_HOURS} hours'
        GROUP BY state_type
        """
    )


def _etl_last_flow_run_statement():
    # Not restricted to the window: the whole point is to notice a scheduler
    # that stopped, and a stopped scheduler has nothing inside the window.
    return text(
        "SELECT extract(epoch FROM max(start_time)) FROM flow_run"
    )


def _publish_etl_stages(rows) -> None:
    ETL_STAGE_DURATION.clear()
    ETL_STAGE_RUNS.clear()

    for row in rows:
        ETL_STAGE_RUNS.labels(stage=row.stage).set(row.runs)
        if row.avg_seconds is not None:
            ETL_STAGE_DURATION.labels(stage=row.stage, stat="avg").set(row.avg_seconds)
        if row.p95_seconds is not None:
            ETL_STAGE_DURATION.labels(stage=row.stage, stat="p95").set(row.p95_seconds)


def _publish_etl_flows(rows, last_run_epoch) -> None:
    ETL_FLOW_RUNS.clear()
    for row in rows:
        ETL_FLOW_RUNS.labels(state=row.state).set(row.total)

    # Left unset when Prefect has never run a flow at all. Publishing 0 would
    # place the last run at 1970 and make every dashboard read "broken" on a
    # stack that is merely new.
    if last_run_epoch is not None:
        ETL_LAST_FLOW_RUN.set(last_run_epoch)


def _publish_ingestion_states(rows) -> None:
    counts = {state: 0 for state in _TRACKED_INGESTION_STATES}
    for row in rows:
        if row.state in counts:
            counts[row.state] = row.total

    INGESTION_PENDING.set(counts["pending"])
    INGESTION_FAILED.set(counts["failed"])


async def _read_domain(session) -> None:
    # Every read completes before anything is published, so a failure halfway
    # through leaves the previous values intact rather than a mix of both.
    source_rows = (await session.execute(_source_stats_statement())).all()
    state_rows = (await session.execute(_ingestion_states_statement())).all()

    _publish_source_stats(source_rows)
    _publish_ingestion_states(state_rows)


async def _read_etl(session) -> None:
    stage_rows = (await session.execute(_etl_stage_statement())).all()
    flow_rows = (await session.execute(_etl_flow_states_statement())).all()
    last_run_epoch = (await session.execute(_etl_last_flow_run_statement())).scalar()

    _publish_etl_stages(stage_rows)
    _publish_etl_flows(flow_rows, last_run_epoch)


async def refresh_domain_metrics(session_factory=None, *, force: bool = False) -> bool:
    """
    Re-read the Syndra domain gauges, at most once every TTL.

    Returns True when the database was actually queried, False when the call was
    served from the cache or the read failed. Never raises: /metrics has to keep
    serving the HTTP histograms even with Postgres down, because those are the
    numbers a latency chapter is built from.
    """
    return await _domain_refresh.run(
        session_factory or AsyncSessionLocal, _read_domain, force=force
    )


async def refresh_etl_metrics(session_factory=None, *, force: bool = False) -> bool:
    """
    Re-read the ETL gauges from Prefect's database, at most once every TTL.

    Same contract as refresh_domain_metrics, and deliberately a separate call
    with a separate cache: the two read different databases, and one being down
    says nothing about the other.
    """
    return await _etl_refresh.run(
        session_factory or PrefectSessionLocal, _read_etl, force=force
    )
