## Incident 008: State Inconsistency in Ingestion State Machine (False Positives)

**Symptom:** After executing the orchestrator (`make run-etl`), the PostgreSQL insertion log showed success, but the AI enrichment script did not process any articles.

**Root Cause:** Misalignment in state contracts. The Data Loader saved new articles with `ingestion_state = 'loaded'`, while the ML node performed a query looking for articles in the `pending` state (`select(RawArticle).where(RawArticle.ingestion_state == 'pending')`).

**Resolution Applied:** Updated the SQLAlchemy query in enrich_sentiment.py to listen for the correct state (`loaded`). Additionally, the `batch_size` was increased to 200 to process the accumulated backlog.
