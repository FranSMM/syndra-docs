"""
Tests for ticker extraction precision.

Every false-positive case below was taken from a real production headline, not
invented. Before the fix, 29.4% of all ticker attachments in the corpus came
from 1-2 character symbols, and 7,451 articles carried nothing but those.

Needs no running stack: the extractor only reads the bundled dictionary.
"""
import pytest

from app.services.ticker_extractor import TickerExtractor


@pytest.fixture(scope="module")
def tx():
    return TickerExtractor()


# --- false positives that used to fire, all from real headlines --------------

@pytest.mark.parametrize(
    "headline, must_not_contain",
    [
        ("The Smartest S&P 500 ETF to Buy With $1,000 Right Now", {"S", "P"}),
        ("U.S. banks report profit uptick in first quarter: FDIC", {"U", "S"}),
        ("U.A.E. Asks U.S. for a Wartime Financial Lifeline", {"U", "A", "E", "S"}),
        ("Is BlackBerry Limited (BB) A Good Stock To Buy Now?", {"A"}),
        ("SK Hynix set for marquee US debut in test for AI appetite", {"AI"}),
        ("Is Wall Street Bullish or Bearish on W.W. Grainger Stock?", {"BLSH"}),
        ("The Dow hits a record as most of Wall Street rises", {"DOW"}),
        # NDAQ was a regression introduced by the alias trimming: the stored
        # alias "Nasdaq," never matched prose, and the trimmed "Nasdaq" then
        # matched every index reference. 673 articles before it was caught.
        ("Stock market today: Dow hits record, S&P 500, Nasdaq slip", {"NDAQ", "DOW"}),
        ("The Nasdaq-100 Squeeze is On. Technical Signals to Watch.", {"NDAQ"}),
        ("Best CD rates today (best account provides 4.05% APY)", {"CD"}),
    ],
)
def test_common_english_does_not_yield_tickers(tx, headline, must_not_contain):
    found = set(tx.extract(headline))
    assert not (found & must_not_contain), (
        f"{sorted(found & must_not_contain)} extracted from ordinary prose"
    )


# --- real mentions must survive ---------------------------------------------

@pytest.mark.parametrize(
    "headline, expected",
    [
        ("Huron Consulting Group (HURN) Slid Amid Concerns Over AI Disruption", "HURN"),
        ("Coinbase Readies For Earnings. Bitcoin, Miners Jump On AI Trade.", "COIN"),
        ("Is Patterson-UTI Energy, Inc. (PTEN) A Good Stock To Buy Now?", "PTEN"),
        ("Bank of America sends blunt message to Nvidia stock investors", "NVDA"),
    ],
)
def test_genuine_mentions_are_still_extracted(tx, headline, expected):
    assert expected in tx.extract(headline)


def test_short_tickers_are_found_by_company_name(tx):
    """
    Withholding the bare symbol must not lose the company. Agilent, SentinelOne
    and Unity are all 1-character tickers; naming them has to still work.
    """
    assert "A" in tx.extract("Agilent Technologies beat expectations this quarter")
    assert "S" in tx.extract("Sentinelone, Inc. reported record annual recurring revenue")
    assert "U" in tx.extract("Unity Software shares climbed after the engine update")


def test_the_known_cost_is_the_bare_short_symbol_in_a_ticker_list(tx):
    """
    Documents what the rule gives up, so it is a recorded trade rather than a
    surprise: a 1-2 character ticker mentioned only as a bare symbol, with the
    company never named, is no longer matched. Measured as rare: GT did not
    reach the top 15 of removed symbols, and accepted in exchange for removing
    847 noise attachments per 4,000 headlines.
    """
    assert "GT" not in tx.extract("Market Digest: MKL, AVY, FISV, GT, XEL")
    # the unambiguous symbols in the same list are unaffected
    assert {"MKL", "AVY", "XEL"} <= set(tx.extract("Market Digest: MKL, AVY, FISV, GT, XEL"))


def test_empty_input(tx):
    assert tx.extract("") == []


def test_warrants_and_preferred_series_do_not_absorb_company_news(tx):
    """
    An article about Morgan Stanley was tagging MS-PL, a preferred series,
    rather than the common stock. Warrants (-WT) and preferred classes (-P*)
    are derivative instruments that never carry the company's news; ordinary
    share classes such as BRK.B are genuine securities and stay registered.
    """
    found = set(tx.extract("Morgan Stanley Maintains Overweight Rating on Aon plc"))
    assert "MS-PL" not in found
    assert not any(t.endswith("-WT") for t in found)
