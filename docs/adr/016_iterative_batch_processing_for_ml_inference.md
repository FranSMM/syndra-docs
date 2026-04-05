## ADR 016: Iterative Batch Processing for ML Inference

**Status:** Accepted

**Context:** The `enrichment_sentiment.py` script initially processed a single batch of 200 articles. High-volume ingestion days caused pending articles to accumulate silently, creating a "zombie" backlog that consumed resources without providing value.

**Decision:** Implemented a `while True` loop that fetches, processes and commits articles in iterative batches of 200, breaking only when the database returns 0 pending rows.

**Rationale:** Prvents pipeling choking. By commiting to the database afted each batch, we maintain a small memory footprint and ensure transactional safety. If the script crashes on batch 4, batch 1-3 are already persisted as `processed` and the script can be restarted from where it left off.
