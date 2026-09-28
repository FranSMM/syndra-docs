# ADR 035: Response Caching and Thread Offloading for Semantic Search

**Status:** Accepted
**Extends:** [ADR 028](./028_native_auth_cache_rate_limiting.md), [ADR 032](./032_per_client_response_cache_isolation.md), [ADR 014](./014_cpu_isolation_for_semantic_embeddings.md)

## Context

`GET /api/v1/search/semantic` was the only public endpoint with no response cache, while `GET /api/v1/sentiment/{ticker}` had one from the start. It is also the more expensive of the two: every request paid for a full `all-MiniLM-L6-v2` forward pass plus a Qdrant vector query, with no reuse across identical queries.

A second, less obvious problem sat in the same handler. Both `SentenceTransformer.encode()` and `qdrant_client.query_points()` are **blocking** calls, invoked directly inside an `async def` route. An async handler that blocks does not yield to the event loop, so the entire worker stalls for the duration of the inference. Effective API concurrency was therefore capped at the number of uvicorn workers (2 in production), regardless of how many requests were in flight. Under concurrent search load, requests to `/sentiment` and `/health` queued behind embedding computations they had nothing to do with.

## Decision

**1. Cache semantic search responses in Redis, 300s TTL.** Matching the sentiment endpoint. Vectors only change when the hourly vectorization backfill runs, so a 5-minute TTL cannot serve data that is meaningfully stale.

**2. Fingerprint the query rather than embedding it in the key verbatim.** Free-text input carries arbitrary length, whitespace and separator characters: none of which belong in a Redis key. The key uses a truncated SHA-256 of the normalized (`strip().lower()`) query:

```
search:{client_name}:{sha256(query)[:16]}:{ticker or '-'}:{limit}
```

Normalization is a deliberate side benefit: `"Apple earnings"`, `"apple earnings"` and `" Apple Earnings "` collapse onto one cache entry. Scoping remains per-client, consistent with ADR 032.

**3. Offload both blocking calls with `asyncio.to_thread`.** The embedding computation and the Qdrant query run in the default thread pool, so the event loop stays free to serve other requests while inference proceeds.

## Trade-off Analysis

| Concern | Before | After |
|---------|--------|-------|
| Repeat query cost | Full embedding + Qdrant query | Single Redis `GET` |
| Event loop during inference | Blocked | Free |
| Concurrency ceiling | Number of uvicorn workers | Thread pool size |
| Redis memory | 0 | ~1KB per distinct (client, query, ticker, limit) |

## Consequences

- **Positive:** Repeated searches, the common case in a demo or dashboard, where users retype similar queries, cost one Redis round-trip instead of a model forward pass.
- **Positive:** Slow searches no longer degrade unrelated endpoints. This matters most on the VPS, where the API container is capped at 512MB and 2 workers.
- **Negative:** Thread offloading does not make inference itself faster; it only stops it monopolizing the loop. The model still runs on CPU by design (ADR 014).
- **Negative:** Cache keys are opaque. Debugging a specific cached entry means recomputing the fingerprint rather than reading the query off the key. Accepted, the query is logged in full on every cache miss and hit.
- **Note:** `asyncio.to_thread` releases the GIL only for the parts of PyTorch that drop it (most tensor ops do). Genuine CPU parallelism across many concurrent searches is still bounded; the fix targets responsiveness, not throughput.

## Measured 06/08/2026

Same query issued twice against the local stack:

| | latency |
|---|---|
| cache miss | 15,678 ms |
| cache hit | 17 ms |

The miss figure is dominated by the **lazy load of the embedding model on first use**, not by the search itself: the singleton in `embedding_service.py` builds on the first call (ADR 026). A warm miss is far cheaper. The number worth taking from this is the hit: 17 ms, served entirely from Redis.

Query normalization was confirmed in the same run: `"nvidia earnings beat"` and `" NVIDIA Earnings Beat "` resolved to a single cache entry rather than two.

**Operational consequence:** the first semantic search after any API restart pays the model load. If that ever matters for a demo, warm it at startup, but not by default, since eagerly loading ~90MB on every boot is exactly what ADR 026 avoided.
