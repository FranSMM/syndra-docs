## ADR 012: GIN Indexing on Nested JSONB Arrays

**Status:** Accepted

**Context:** The `raw_articles` table stores critical financial metadata (sentiment, extracted tickers) inside a schema-less `JSONB` payload to accommodate varying web structures. However, querying for a specific ticker requires scanning the entire JSON tree. At 50,000+ rows, standard `Seq Scan` operations would severely breach out API's strict latency requirements (< 200ms p95).

**Decision:** Implement a GIN (Generalized Inverted Index) index specifically targeting the exact nested array path: `(payload -> 'financial_metadata' -> 'tickers')`.

**Consequences:** This approach avoids the massive disk overhead of indexing the entire JSONB column. By targeting only the queryable nodes, we achieve relational-grade performance (sub-50ms lookups via Bitmap Index Scan) without sacrificing the fast-iteration benefits of the Bronze Layer's JSONB design.
