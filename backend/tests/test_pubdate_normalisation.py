"""
Tests for the RSS date normalisation in GenericRssSpider.

These exist because the bug they cover was invisible: RSS 2.0 mandates RFC 822
dates, Pydantic v2 only parses ISO 8601, and the spider caught the resulting
ValidationError and moved on. Standards-compliant feeds therefore produced zero
articles while the pipeline reported success. Yahoo Finance was the only source
that ever worked, and only because it emits ISO 8601 instead.

No running stack needed: this is pure string handling plus the real schema.
"""
from datetime import timezone

import pytest
from pydantic import ValidationError

from app.schemas.article_schema import ScrapedArticle
from app.scraper.scraper.spiders.generic_rss import normalise_pub_date


def _build(pub: str) -> ScrapedArticle:
    """Feed a date through the schema exactly as the spider does."""
    return ScrapedArticle(
        id=ScrapedArticle.generate_id("https://example.test/a"),
        url="https://example.test/a",
        source="test_feed",
        source_type="rss_feed",
        title="A sufficiently long headline",
        published_at=normalise_pub_date(pub),
        payload={"description": "d"},
    )


@pytest.mark.parametrize(
    "raw",
    [
        "Wed, 12 Aug 2026 19:36:21 -0400",   # the RSS 2.0 standard form
        "Tue, 12 Aug 2026 14:30:00 GMT",     # GMT rather than an offset
        "Tue, 12 Aug 2026 14:30:00 +0000",   # explicit zero offset
        "12 Aug 2026 14:30:00 +0200",        # no weekday, which RFC 822 permits
    ],
)
def test_rfc822_dates_are_accepted(raw):
    """Every one of these was silently dropped before the fix."""
    assert _build(raw).published_at is not None


@pytest.mark.parametrize(
    "raw",
    [
        "2026-08-12T17:47:00Z",              # what Yahoo Finance emits
        "2026-08-12T17:47:00+02:00",
    ],
)
def test_iso_dates_still_pass_through(raw):
    """The fix must not break the one source that already worked."""
    assert _build(raw).published_at is not None


def test_offset_is_preserved_not_invented():
    """An explicit offset must survive normalisation unchanged."""
    art = _build("Wed, 12 Aug 2026 19:36:21 -0400")
    assert art.published_at.utcoffset().total_seconds() == -4 * 3600


def test_missing_timezone_is_assumed_utc():
    """
    RFC 822 allows omitting the offset. Assuming UTC is a deliberate choice:
    documented in normalise_pub_date, because the alternative is discarding
    the item, and the storage layer treats timestamps as naive UTC anyway.
    """
    art = _build("Wed, 12 Aug 2026 19:36:21")
    assert art.published_at.utcoffset() == timezone.utc.utcoffset(None)


def test_unparseable_input_is_left_for_pydantic_to_reject():
    """
    Garbage must not be silently coerced into a plausible date. The normaliser
    hands it through untouched and the schema rejects it, which is the correct
    failure: a wrong timestamp is worse than a missing article.
    """
    assert normalise_pub_date("not a date at all") == "not a date at all"
    with pytest.raises(ValidationError):
        _build("not a date at all")


def test_empty_input_is_returned_unchanged():
    assert normalise_pub_date("") == ""
