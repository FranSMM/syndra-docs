# ADR 028: Native Authentication, Cache, and Rate Limiting (Zero Third-Party Dependencies)

**Status:** Accepted, rate limiting mechanism superseded by [ADR 034](./034_atomic_rate_limiting_lua_script.md)

## Context
The B2B service layer required high-speed authentication, response caching, and abuse protection. An initial attempt to integrate `fastapi-cache2` triggered a catastrophic dependency conflict, forcing a pinned ancient version of `redis` that was incompatible with the async stack (`aioredis`). Third-party middleware libraries introduced unpredictable coupling with FastAPI's lifecycle.

## Decision
All three concerns were implemented natively, without any third-party FastAPI middleware:

1. **Authentication:** API keys are generated via `secrets.token_urlsafe(32)` and stored as irreversible SHA-256 hashes in PostgreSQL. The raw key is displayed exactly once during client provisioning and is never persisted. Subsequent requests are validated by hashing the incoming `X-API-Key` header and comparing against the stored hash.
2. **Response Caching:** Implemented directly in FastAPI route handlers using `aioredis`. Cache keys are scoped per-client (`cache:{client_hash}:{endpoint}:{params}`) to prevent Cross-Client Data Leakage. TTLs are set per-endpoint based on data freshness requirements.
3. **Rate Limiting:** 100 requests per 60-second fixed window, keyed on the API key hash. Critically, rate limiting is enforced **post-authentication**, invalid API keys are rejected before consuming any rate budget, preventing resource exhaustion attacks.

   > **Superseded.** This ADR originally specified an `INCR` + `EXPIRE` command pair and described it as atomic. It is not: the two are separate round-trips, and a failure between them orphans the counter with no TTL, permanently locking out the client (see [INC-019](../troubleshooting/019_orphaned_rate_limit_key_without_ttl.md)). The mechanism was replaced by an atomic Lua script in [ADR 034](./034_atomic_rate_limiting_lua_script.md). The *policy* described here, the limit, the window, and post-authentication enforcement, is unchanged.

## Consequences
- **Positive:** Zero dependency debt. Complete control over cache invalidation and rate window semantics.
- **Positive:** Fast request pipeline. On the fully-cached authenticated path the cost is three Redis round-trips: the auth lookup, the rate limiter, and the response cache read.

  > **Correction.** This originally claimed a "single Redis round-trip for cached + authenticated requests". That was never accurate: the limiter alone issued three (`INCR`, `EXPIRE`, `TTL`), for five in total. ADR 034 collapses the limiter to one, giving the three stated above.

- **Negative:** Requires manual implementation of cache eviction strategies for new endpoints. No declarative decorator pattern, caching logic lives in route handlers. This is what allowed `/search/semantic` to ship with no cache at all until [ADR 035](./035_semantic_search_caching_and_offloading.md).
- **Negative:** The window is fixed, not sliding, despite the original wording. A client can burst 200 requests across a window boundary. Accepted deliberately in ADR 034.
