## Incident 015: Silent Accumulation of Pending Articles (Pipeline Choke)

**Symptom:** 50+ articles remained indefinitely stuck with `ingestion_state: 'pending'`. Consequently, the Gold Layer (Qdrant) contained dirty records with `tickers: []`, `sentiment_label: null`, and `sentiment_score: null`.

**Root Cause:** Two logical bugs in `enrich_sentiment.py`:

**State Misalignment:** The script queried for articles where `ingestion_state == 'loaded'`, whereas the Scrapy pipeline correctly inserts them as `'pending'`. FinBERT starved because it looked in the wrong queue.

**Lack of Pagination:** The script processed a single batch of 200 articles and exited without a loop. During high-volume news days, anything beyond the first 200 articles was abandoned.

**Resolution:**

**Code Fix:** Corrected the filter to query for `'pending'`.

**Code Fix:** Wrapped the FinBERT inference block in a `while True` loop that consumes batches iteratively, breaking only when the SQLAlchemy query returns an empty list.

**Manual Recovery:** Executed `python -m app.ml.enrich_sentiment` (processed the 50 pending) followed by `python -m app.pipeline.backfill_vectors` (synced the new vectors to Qdrant).

**Architectural Lesson:** This is a classic "Silent Failure". In production, as Scrapy ingests more data, the pending queue would grow unnoticed until B2B clients complained about stale data. This mandates the creation of a Prometheus metric and Grafana alert in Phase 6: trigger a P1 Alert if `COUNT(*) FROM raw_articles WHERE ingestion_state = 'pending'` exceeds a predefined threshold for more than 2 hours.

