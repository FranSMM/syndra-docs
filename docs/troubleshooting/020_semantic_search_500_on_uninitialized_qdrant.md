## Incident 020: Semantic Search Returns HTTP 500 on a Freshly Provisioned Qdrant

**Symptom:** On a new deployment (or after a Qdrant volume wipe / disaster recovery restore), `GET /api/v1/search/semantic` returns `HTTP 500 Internal search engine error` for every query, while `/health` and `/api/v1/sentiment/{ticker}` behave normally. The API logs show a Qdrant client error about a missing collection.

**Root Cause:** `init_qdrant_collection()` exists in `app/db/vector_store.py` and is idempotent, but nothing in the API called it. The FastAPI app had no startup hook. In practice the collection got created as a side effect of the *vectorization backfill*, so whether semantic search worked depended entirely on whether the scheduler container happened to run a full pipeline cycle before the first search request arrived.

That ordering held on the existing VPS by accident and broke on a clean provision. Classic implicit dependency: the API consumed a resource whose creation it delegated, by coincidence, to an unrelated container.

**Resolution:** Added a FastAPI `lifespan` handler in `app/main.py` that calls `init_qdrant_collection()` before the app accepts traffic. Three deliberate details:

1. **Idempotent by design.** `init_qdrant_collection()` already checks for the collection's existence and Qdrant silently ignores duplicate `create_payload_index` calls, so running it on every boot is free.
2. **Runs in a worker thread.** The Qdrant client is synchronous. Calling it directly in an async lifespan would block the event loop during startup; `asyncio.to_thread` avoids that.
3. **Failure is non-fatal.** The exception is caught and logged as a warning rather than aborting startup. `/health` and `/sentiment` have no dependency on Qdrant, so a vector-store outage degrades semantic search instead of taking down the entire API, which would otherwise turn a Qdrant hiccup into a total outage, including the health check the VPS relies on.

**Verification:**

```bash
docker compose down -v && docker compose up -d
docker compose logs api | grep -i qdrant   # expect the collection/index init lines
curl -s "http://localhost:8000/api/v1/search/semantic?query=apple%20earnings" \
  -H "X-API-Key: $RAW_KEY"                 # expect 200 with [] , not 500
```

**Architectural Lesson:** An idempotent initialization routine that nothing calls is not initialization, it is dead code that happens to be reachable from somewhere else. Any resource the API *reads* on the request path should be ensured by the API itself at startup, not left to whichever container gets there first. The corollary matters just as much: startup initialization for a *non-critical* dependency must not be fatal, or you convert a partial degradation into a full outage.
