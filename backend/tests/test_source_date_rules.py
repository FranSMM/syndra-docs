"""
Unit tests for the per-source publication-date rules.

These exist because the generic guard in app/core/dates.py cannot see one real
failure. The SEC's newsroom feed carries 1990s press releases stamped with the
current year. Two of them claimed a date months after we ingested them and were
caught. A third: release 99-110, "President's Year 2000 Council", was dated
2026-09-07, which is before we read it and therefore perfectly plausible. It sat
in the corpus counted as a recent signal.

What catches it is that the SEC numbers every release YEAR-NUMBER and puts that
number in the URL, so the release carries its own true year.
"""
from datetime import datetime

import pytest

from app.core.source_rules import has_implausible_publication_year

SEC = "sec_press_releases"


@pytest.mark.parametrize(
    "url, year, expected",
    [
        # The three real articles that started this.
        ("https://www.sec.gov/newsroom/press-releases/99-110-presidents-year-2000-council", 2026, True),
        ("https://www.sec.gov/newsroom/press-releases/97-114-municipal-securities-underwriters", 2026, True),
        ("https://www.sec.gov/newsroom/press-releases/97-99-sec-chairman-arthur-levitt-iowa", 2026, True),
        # Current releases, which are the overwhelming majority and must pass.
        ("https://www.sec.gov/newsroom/press-releases/2026-88-sec-grants-exemptive-relief", 2026, False),
        ("https://www.sec.gov/newsroom/press-releases/2026-53-sec-establishes-joint-data", 2026, False),
        # A two-digit release read with its real year is consistent, not a bug.
        ("https://www.sec.gov/newsroom/press-releases/99-110-presidents-year-2000-council", 1999, False),
    ],
)
def test_sec_release_number_decides(url, year, expected):
    published = datetime(year, 9, 7, 12, 0, 0)
    assert has_implausible_publication_year(SEC, url, published) is expected


def test_two_digit_years_map_across_the_century_boundary():
    """SEC release numbering ran on two digits until the early 2000s."""
    old = "https://www.sec.gov/newsroom/press-releases/97-114-x"
    recent = "https://www.sec.gov/newsroom/press-releases/01-42-x"
    assert has_implausible_publication_year(SEC, old, datetime(1997, 1, 1)) is False
    assert has_implausible_publication_year(SEC, recent, datetime(2001, 1, 1)) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://www.sec.gov/newsroom/press-releases/no-number-here",
        "https://www.sec.gov/litigation/something-else",
        "https://www.sec.gov/",
        "",
    ],
)
def test_a_url_without_a_release_number_is_left_alone(url):
    """
    No number means no opinion. The rule may only ever reject on evidence;
    absence of evidence must not start discarding real articles.
    """
    assert has_implausible_publication_year(SEC, url, datetime(2026, 9, 7)) is False


def test_other_sources_are_untouched():
    """
    69,962 of 70,001 articles come from two feeds this rule knows nothing about.
    A URL that happens to contain digits must not trip it.
    """
    for source in ("global_finance_rss", "bbc_business", "anything_a_client_adds"):
        url = "https://finance.yahoo.com/news/97-114-some-story-about-2026"
        assert has_implausible_publication_year(source, url, datetime(2026, 9, 7)) is False


def test_a_missing_date_has_nothing_to_contradict():
    url = "https://www.sec.gov/newsroom/press-releases/99-110-x"
    assert has_implausible_publication_year(SEC, url, None) is False
