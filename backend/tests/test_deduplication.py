"""
Unit tests for the Late Deduplication logic in the serving layer (ADR 033).

Unlike test_security.py, these tests need no running stack: the DB session is
stubbed, so the SQLAlchemy statement is built but never executed. That keeps the
most subtle logic in the codebase: the title/sentiment/time dedup heuristic,
covered by a suite that runs anywhere, including CI without services.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.sentiment_service import fetch_recent_signals

# Marked explicitly rather than relying on `asyncio_mode = auto` in pytest.ini.
# That file is not copied into the API image nor mounted by Compose, so inside
# the container, which is the documented way to run the suite, pytest falls
# back to strict mode and every async test here errors with "async def functions
# are not natively supported". The marker makes the file work in both places.
pytestmark = pytest.mark.asyncio

BASE = datetime(2026, 7, 26, 12, 0, 0)


def make_article(title, label="neutral", score=0.0, minutes_ago=0, url="https://www.reuters.com/x"):
    """Minimal stand-in for a Silver Layer Article row."""
    return SimpleNamespace(
        title=title,
        sentiment_label=label,
        sentiment_score=score,
        published_at=BASE - timedelta(minutes=minutes_ago),
        source="global_finance_rss",
        raw_article=SimpleNamespace(url=url),
    )


class _StubResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def unique(self):
        return self

    def all(self):
        return self._rows


class _StubSession:
    """Returns a fixed row set regardless of the statement it is handed."""

    def __init__(self, rows):
        self._rows = rows

    async def execute(self, stmt):
        return _StubResult(self._rows)


async def _titles(rows, **kwargs):
    signals = await fetch_recent_signals(_StubSession(rows), "NVDA", **kwargs)
    return [s.title for s in signals]


async def test_reprint_within_window_is_discarded():
    """Same story, same sentiment, 30 minutes apart: a reprint, not a new signal."""
    rows = [
        make_article("Nvidia stock rises 5% on earnings beat", "positive", 0.8, 0),
        make_article("Nvidia stock rises 5% on earnings beat!", "positive", 0.8, 30),
    ]
    assert await _titles(rows, limit=5) == ["Nvidia stock rises 5% on earnings beat"]


async def test_opposite_sentiment_survives_deduplication():
    """
    The ML safety net from ADR 033: near-identical headlines carrying opposite
    FinBERT labels are contrary signals and must both reach the client.
    """
    rows = [
        make_article("Nvidia falls 5% after guidance", "negative", -0.7, 0),
        make_article("Nvidia rises 5% after guidance", "positive", 0.7, 30),
    ]
    assert len(await _titles(rows, limit=5)) == 2


async def test_temporal_evolution_survives_deduplication():
    """Identical headline 10 hours later is a follow-up, outside the 3h window."""
    rows = [
        make_article("Nvidia stock rises on earnings beat", "positive", 0.8, 0),
        make_article("Nvidia stock rises on earnings beat", "positive", 0.8, 60 * 10),
    ]
    assert len(await _titles(rows, limit=5, dedup_window_hours=3)) == 2


async def test_tie_breaker_prefers_the_longer_headline():
    """On an exact timestamp collision, the more informative title wins in place."""
    short = make_article("Nvidia stock rises on strong earnings", "positive", 0.8)
    long = make_article("Nvidia stock rises on strong earnings beat", "positive", 0.8)
    short.published_at = BASE
    long.published_at = BASE

    assert await _titles([short, long], limit=5) == [
        "Nvidia stock rises on strong earnings beat"
    ]


async def test_deduplicate_false_disables_filtering():
    rows = [
        make_article("Nvidia stock rises 5% on earnings beat", "positive", 0.8, 0),
        make_article("Nvidia stock rises 5% on earnings beat", "positive", 0.8, 30),
    ]
    assert len(await _titles(rows, limit=5, deduplicate=False)) == 2


async def test_limit_is_respected():
    headlines = [
        "Apple unveils new silicon lineup at fall event",
        "Tesla recalls thousands of vehicles over brake fault",
        "Federal Reserve holds interest rates steady",
        "Oil slumps as demand forecasts weaken",
        "Microsoft closes acquisition of gaming studio",
    ]
    rows = [make_article(h, minutes_ago=i * 10) for i, h in enumerate(headlines)]
    assert await _titles(rows, limit=3) == headlines[:3]


async def test_source_is_derived_from_the_article_url():
    rows = [make_article("Nvidia beats expectations", url="https://www.bloomberg.com/news/x")]
    signals = await fetch_recent_signals(_StubSession(rows), "NVDA", limit=5)
    assert signals[0].source == "Bloomberg.com"


async def test_missing_raw_article_falls_back_to_the_source_column():
    row = make_article("Nvidia beats expectations")
    row.raw_article = None
    signals = await fetch_recent_signals(_StubSession([row]), "NVDA", limit=5)
    assert signals[0].source == "global_finance_rss"
    assert signals[0].url is None


async def test_empty_result_set_returns_no_signals():
    assert await _titles([], limit=5) == []
