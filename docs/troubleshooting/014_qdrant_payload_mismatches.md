## Incident 014: Qdrant Payload Mismatches (Null Returns)

**Symptom:** Semantic search endpoints return `null` for tickers and `"unknown"` for `title` within the JSON response array.

**Root Cause:** Dictionary key mismatch during the vector backfill process. The script queried the payload using `.get("ticker")` instead of the plural `"tickers"` established in the DB schema. Furthermore, the `title` was mathematically encoded into the vector but completely omitted from the Qdrant PointStruct payload mapping.

**Resolution:** Updated `backfill_vectors.py` to strictly mirror the exact DB schema keys. Explicitly appended the `title` variable to the Qdrant payload dictionary during the batch upsert.
