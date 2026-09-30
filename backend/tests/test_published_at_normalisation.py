"""
Unit tests for the Bronze -> Silver publication-date normalisation.

Distinct from test_pubdate_normalisation.py, which covers the *ingestion* side:
turning an RFC 822 <pubDate> into something Pydantic accepts before it reaches
Bronze. This covers the next boundary along: reading that stored string back
out and deciding what Silver should hold.

Two failures found in production on 15/09/2026 motivate the whole module:

1. The offset was discarded rather than converted. "07:00:00-05:00" was stored
   as 07:00 instead of 12:00, putting all 39 SEC articles five hours early,
   wider than the 3h deduplication window they are compared against.
2. Three 1990s SEC press releases arrived from the feed dated 2026. Two of them
   claimed a publication date after we had already ingested them, which cannot
   be true of anything.
"""
from datetime import datetime

import pytest

from app.core.dates import normalise_published_at

INGESTED = datetime(2026, 9, 11, 3, 19, 42)


def test_utc_input_keeps_its_wall_clock():
    """The two working feeds emit Z. The fix must not move them by a second."""
    assert normalise_published_at("2026-09-15T07:20:55Z") == datetime(2026, 9, 15, 7, 20, 55)


def test_negative_offset_is_converted_not_discarded():
    """
    The actual bug. The SEC emits -05:00; 07:00 there is 12:00 UTC.
    Storing 07:00 is not a rounding difference, it is a different instant.
    """
    assert normalise_published_at("2026-09-10T07:00:00-05:00") == datetime(2026, 9, 10, 12, 0, 0)


def test_positive_offset_is_converted():
    assert normalise_published_at("2026-09-10T14:30:00+02:00") == datetime(2026, 9, 10, 12, 30, 0)


def test_naive_input_is_assumed_utc():
    """
    Consistent with the ingestion-side normaliser, which documents the same
    assumption. Better a stated assumption than discarding the item.
    """
    assert normalise_published_at("2026-09-10T12:00:00") == datetime(2026, 9, 10, 12, 0, 0)


@pytest.mark.parametrize("raw", [None, "", "not a date", "2026-13-45T99:99:99Z"])
def test_unusable_input_yields_none(raw):
    assert normalise_published_at(raw) is None


def test_published_after_ingestion_is_rejected():
    """
    Press release 97-114, which the SEC's feed dated 2026-12-16 and we ingested
    on 2026-09-11. Nothing can be published three months after being read.

    Rejected to None rather than kept: a wrong timestamp is worse than a missing
    one, because everything downstream trusts it. None keeps the article and its
    sentiment while excluding it from time-window queries and from the source
    freshness gauge.
    """
    assert normalise_published_at("2026-12-16T07:00:00-05:00", ingested_at=INGESTED) is None


def test_a_little_ahead_of_ingestion_is_tolerated():
    """
    Clock skew between a publisher and this box is real and small. The guard is
    for dates that cannot be true, not for dates that are merely surprising.
    """
    slightly_ahead = "2026-09-11T03:40:00Z"       # 20 minutes after ingestion
    assert normalise_published_at(slightly_ahead, ingested_at=INGESTED) is not None


def test_an_old_article_is_kept():
    """
    Press release 99-110 is from 1999 and the feed dated it 2026-09-07: before
    we ingested it, so this guard cannot catch it and must not pretend to.
    Detecting that one needs the release number in the URL, which is source
    specific and deliberately not part of this function.
    """
    assert normalise_published_at("2026-09-07T08:00:00-04:00", ingested_at=INGESTED) == datetime(
        2026, 9, 7, 12, 0, 0
    )


def test_guard_is_skipped_when_ingestion_time_is_unknown():
    """Callers without a Bronze row still get the timezone conversion."""
    assert normalise_published_at("2026-12-16T07:00:00-05:00") == datetime(2026, 12, 16, 12, 0, 0)
