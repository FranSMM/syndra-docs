# ADR-033: Late Deduplication in Serving Layer via SequenceMatcher

## Context
In financial news aggregation, publishers (e.g., Yahoo Finance, Reuters) frequently update an article's headline throughout the trading day to reflect market changes (e.g., *"Nvidia on track for record close"* vs *"Nvidia clinches record close"*). These updates often generate a new URL in the RSS feed. 

Since our ETL pipeline's idempotency key (`content_hash` in the Bronze layer) is derived from the URL and raw payload, the updated article is correctly treated as a new, unique entity in the database. 

While storing the historical evolution of headlines is valuable for data lineage and backtesting, exposing nearly identical headlines with the exact same timestamp in a single API response (`TickerSentimentResponse`) severely degrades the perceived **Data Quality** for downstream B2B clients (Quants and Data Scientists).

## Decision
We will implement **Late Deduplication (Read-Time Filtering)** directly in the Serving Layer (`sentiment_service.py`), utilizing Python's native `difflib.SequenceMatcher` combined with our ML inferences.

1. The database query will "over-fetch" by requesting `limit * 2` articles to ensure a sufficient pool of candidates after filtering.
2. The service will iterate through the results and compare each article's title against previously processed titles in the current request batch.
3. **Semantic Safety Net:** If the similarity ratio is `> 0.85` (85%), the system performs a secondary check on the FinBERT `sentiment_label`. 
   - *Why?* A headline like "Nvidia falls 5% after earnings" is >85% similar to "Nvidia rises 5% after earnings", but their financial meanings are opposite. By requiring the ML `sentiment_label` to be identical, we prevent critical False Positives.
4. **Temporal Evolution Window:** The system enforces a temporal limit based on the client's configuration (e.g., **3 hours** or 10,800 seconds). If two articles are >85% similar and have the same sentiment, but were published more than 3 hours apart (e.g., 09:00 vs 16:00), they are treated as an *evolution* of the news rather than a redundant duplicate, and both are kept.
5. **Freshness Bias via Iteration:** Because the initial SQL query uses `.order_by(Article.published_at.desc())`, the deduplicator processes articles from newest to oldest. The first article added to the `seen` list is mathematically guaranteed to be the freshest/most recent iteration of the headline. Older duplicates are the ones discarded.
6. The service will stop processing once it yields exactly the originally requested `limit` of unique articles.

## Consequences

### Positive
* **Instant Data Quality Boost:** B2B clients will never see visually duplicate headlines in the API payload, preserving absolute trust in the dataset.
* **No Database Migrations Required:** We avoid complex SQL deduplication logic or altering the structural integrity of the Medallion Architecture.
* **Preserves Historical Data:** The Bronze and Silver layers remain completely immutable and retain all iterations of the publisher's headlines.

### Negative
* **Computational Overhead:** `SequenceMatcher` runs in `O(N*M)` time. However, since `N` (the API `limit`) is strictly bounded (maximum 100) by Pydantic validation, the calculation takes mere microseconds in Python and has virtually zero impact on latency.
