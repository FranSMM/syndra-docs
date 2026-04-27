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
* **Evaluated:** The total number of articles fetched from PostgreSQL (usually `limit * 2`).
* **Discarded:** Articles safely removed from the API response because they were >85% similar, had the same FinBERT sentiment, AND occurred within the temporal window.
* **Saved by Sentiment:** Articles that were >85% similar textually (e.g., "Nvidia falls" vs "Nvidia rises") but were kept because FinBERT detected opposing financial semantic meanings. *A high number here proves the value of the ML Safety Net.*
* **Saved by Time:** Articles that were >85% similar and had the same sentiment, but were published outside the temporal window (e.g., 6 hours apart). These are kept because they represent the *evolution* of the news, not spam.

## Tuning the Parameters

### `dedup_window_hours`
This is now a dynamic API query parameter (`?dedup_window_hours=X`), empowering the client to control the filter.

* **High-Frequency Events (Earnings, Fed decisions):** Recommend clients use `dedup_window_hours=1`. In fast-moving markets, identical headlines published 2 hours apart might contain critical updates in the underlying article.
* **Low-Frequency / Macro News:** Recommend clients use `dedup_window_hours=12` or `24`. Macro news tends to be syndicated and recycled heavily over a 24-hour period.
* **Disable Deduplication:** Clients can pass `?deduplicate=false` to completely bypass the filter. The `dedup_window_hours` parameter requires a minimum value of 1.

### Troubleshooting: "Not hitting the Limit"
If the API requests `limit=20` but only returns `15` articles, it means the dataset contained so much spam/duplicates that the `Evaluated` pool (which pulls `limit * 2 = 40`) was exhausted before yielding 20 unique signals. 
* **Fix:** If this occurs frequently, consider increasing the over-fetch multiplier in `sentiment_service.py` from `limit * 2` to `limit * 3`.
