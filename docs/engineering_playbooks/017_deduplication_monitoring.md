# Engineering Playbook 017: Monitoring Serving-Layer Deduplication

## Objective
This playbook outlines how to monitor, interpret, and tune the Semantic Deduplication engine running in the Serving Layer (`sentiment_service.py`). The engine filters out noisy, duplicated headlines in real-time before returning the API payload.

## Accessing Deduplication Logs

The `syndra_api` container outputs structured deduplication metrics via `logger.info` for every request that hits the database (Cache Miss).

To view the live deduplication logs on the VPS or local environment, run:

```bash
# View only the deduplication metrics live
docker logs -f syndra_api | grep "Deduplication Metrics"

# View logs for a specific ticker (e.g., AAPL)
docker logs -f syndra_api | grep "Deduplication Metrics for AAPL"
```

## Understanding the Metrics

A typical log entry looks like this:
`INFO:app.services.sentiment_service:Deduplication Metrics for AAPL (Limit 20, Window 3h) | Evaluated: 40 | Discarded: 4 | Saved by Sentiment: 1 | Saved by Time: 2`

### Metric Definitions:
* **Evaluated:** The total number of articles fetched from PostgreSQL — `limit * DEDUP_OVERFETCH_FACTOR` (currently `limit * 2`), or just `limit` when the client passes `deduplicate=false`.
* **Discarded:** Articles safely removed from the API response because they were >85% similar, had the same FinBERT sentiment, AND occurred within the temporal window.
* **Saved by Sentiment:** Articles that were >85% similar textually (e.g., "Nvidia falls" vs "Nvidia rises") but were kept because FinBERT detected opposing financial semantic meanings. *A high number here proves the value of the ML Safety Net.*
* **Saved by Time:** Articles that were >85% similar and had the same sentiment, but were published outside the temporal window (e.g., 6 hours apart). These are kept because they represent the *evolution* of the news, not spam.

> **Counting change — historical numbers are not comparable.** The two `Saved by ...` counters used to increment once per *comparison* rather than once per *article*. Each incoming article is compared against every article already kept, so a headline that near-matched three earlier ones added three counts while being kept exactly once. The counters were therefore inflated, unboundedly so on tickers with heavy syndication.
>
> They now record at most one count per article, using the first reason it survived. `Discarded + Saved by Sentiment + Saved by Time` is now bounded by `Evaluated`, which it was not before. Expect the `Saved by ...` values to drop on high-volume tickers — that is the fix, not a regression in dedup quality. `Discarded` was always counted per-article and is unaffected.

## Tuning the Parameters

### `dedup_window_hours`
This is now a dynamic API query parameter (`?dedup_window_hours=X`), empowering the client to control the filter.

* **High-Frequency Events (Earnings, Fed decisions):** Recommend clients use `dedup_window_hours=1`. In fast-moving markets, identical headlines published 2 hours apart might contain critical updates in the underlying article.
* **Low-Frequency / Macro News:** Recommend clients use `dedup_window_hours=12` or `24`. Macro news tends to be syndicated and recycled heavily over a 24-hour period.
* **Disable Deduplication:** Clients can pass `?deduplicate=false` to completely bypass the filter. The `dedup_window_hours` parameter requires a minimum value of 1.

### Troubleshooting: "Not hitting the Limit"
If the API requests `limit=20` but only returns `15` articles, there are two distinct causes and they call for opposite responses. The service now logs which one applies, so you no longer have to infer it:

```bash
docker logs -f syndra_api | grep "Short result"
```

* **`INFO ... Silver Layer only holds N matching articles`** — the ticker genuinely has thin coverage. Deduplication is not at fault; the over-fetch pool was never exhausted. Nothing to tune. If the coverage matters commercially, the fix is upstream: add sources to `feeds.json`.
* **`WARNING ... after deduplicating N fetched articles`** — the over-fetch pool *was* exhausted by duplicates before yielding `limit` unique signals. This is the tunable case.
  * **Fix:** raise `DEDUP_OVERFETCH_FACTOR` in `sentiment_service.py` from `2` to `3`. Note the cost is linear in rows fetched but quadratic in comparisons, since each new article is compared against every one already kept.

Before this logging existed, both cases looked identical from the outside: a short response with no explanation, indistinguishable from thin data coverage. That ambiguity is exactly what made under-filled responses easy to dismiss.
