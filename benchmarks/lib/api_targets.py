#!/usr/bin/env python3
"""Writes vegeta targets for the API latency experiment (05) to stdout.

    api_targets.py SCENARIO --base URL --tickers FILE [--slice I --slices N]

Scenarios:
  sentiment_warm  one ticker, always the same: the cache answers
  sentiment_cold  every ticker in turn: each request misses the cache
  search_warm     one semantic query, always the same
  search_cold     ticker + topic queries, each used once per session

The API key is not written here: the caller passes it with vegeta's -header,
so it never touches the disk.
"""
import argparse
import random
import urllib.parse

SEED = 2026
WARM_TICKER = "NVDA"
WARM_QUERY = "semiconductor export restrictions"
TOPICS = [
    "earnings guidance", "analyst downgrade", "supply chain risk", "regulatory probe",
    "dividend increase", "share buyback", "layoffs", "merger talks", "product launch",
    "lawsuit", "revenue miss", "record quarter",
]


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]


def sentiment_url(base, ticker):
    return f"{base}/api/v1/sentiment/{urllib.parse.quote(ticker)}"


def search_url(base, query):
    return f"{base}/api/v1/search/semantic?query={urllib.parse.quote(query)}"


def build_urls(scenario, base, tickers, slice_index, slices):
    if scenario == "sentiment_warm":
        return [sentiment_url(base, WARM_TICKER)]
    if scenario == "sentiment_cold":
        return [sentiment_url(base, t) for t in tickers]
    if scenario == "search_warm":
        return [search_url(base, WARM_QUERY)]
    if scenario == "search_cold":
        # A fixed shuffle split into disjoint slices: repeatable across sessions,
        # never repeated within one, so no query can hit the previous run's cache.
        pool = [f"{t} {topic}" for t in tickers for topic in TOPICS]
        random.Random(SEED).shuffle(pool)
        size = len(pool) // slices
        start = (slice_index % slices) * size
        return [search_url(base, q) for q in pool[start:start + size]]
    raise SystemExit(f"unknown scenario: {scenario}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario")
    parser.add_argument("--base", required=True)
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--slice", type=int, default=0, dest="slice_index")
    parser.add_argument("--slices", type=int, default=1)
    args = parser.parse_args()

    urls = build_urls(args.scenario, args.base.rstrip("/"), read_lines(args.tickers),
                      args.slice_index, args.slices)
    for url in urls:
        print(f"GET {url}")


if __name__ == "__main__":
    main()
