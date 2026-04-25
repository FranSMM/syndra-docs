# ADR 028: Native Authentication, Cache, and Rate Limiting (Zero Third-Party Dependencies)

**Status:** Accepted

## Context
The B2B service layer required high-speed authentication, response caching, and abuse protection. An initial attempt to integrate `fastapi-cache2` triggered a catastrophic dependency conflict, forcing a pinned ancient version of `redis` that was incompatible with the async stack (`aioredis`). Third-party middleware libraries introduced unpredictable coupling with FastAPI's lifecycle.

## Decision
All three concerns were implemented natively, without any third-party FastAPI middleware:

1. **Authentication:** API keys are generated via `secrets.token_urlsafe(32)` and stored as irreversible SHA-256 hashes in PostgreSQL. The raw key is displayed exactly once during client provisioning and is never persisted. Subsequent requests are validated by hashing the incoming `X-API-Key` header and comparing against the stored hash.
2. **Response Caching:** Implemented directly in FastAPI route handlers using `aioredis`. Cache keys are scoped per-client (`cache:{client_hash}:{endpoint}:{params}`) to prevent Cross-Client Data Leakage. TTLs are set per-endpoint based on data freshness requirements.
3. **Rate Limiting:** Uses Redis's atomic `INCR` + `EXPIRE` pattern (100 requests per 60-second sliding window). Critically, rate limiting is enforced **post-authentication** — invalid API keys are rejected before consuming any rate budget, preventing resource exhaustion attacks.

## Consequences
- **Positive:** Ultra-fast request pipeline (single Redis round-trip for cached + authenticated requests). Zero dependency debt. Complete control over cache invalidation and rate window semantics.
- **Negative:** Requires manual implementation of cache eviction strategies for new endpoints. No declarative decorator pattern — caching logic lives in route handlers.
