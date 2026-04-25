# ADR 030: Redis as the Unified Session-State Backend

**Status:** Accepted

## Context
The B2B service layer introduced three distinct stateful concerns at the edge: authentication caching, response caching, and rate limiting. Each of these required a fast, shared, in-memory store accessible by multiple API worker processes. Using separate backends for each concern (e.g., in-process dictionaries for caching, a dedicated rate limiter service) would have multiplied operational complexity and memory footprint on the VPS.

## Decision
Redis was adopted as the **single, unified backend** for all ephemeral session-state:

| Concern | Key Pattern | TTL | Operation |
|---------|-------------|-----|-----------|
| Auth Cache | `auth:{key_hash}` | 5 min | `GET` / `SET` |
| Response Cache | `cache:{client_hash}:{endpoint}:{params}` | Varies by endpoint | `GET` / `SETEX` |
| Rate Limiting | `ratelimit:{key_hash}` | 60s (sliding window) | `INCR` / `EXPIRE` |

All interactions use `aioredis` (async-native) to avoid blocking the FastAPI event loop. Redis runs as a dedicated container in the Docker Compose stack with no persistence (`--save ""`) since all data is ephemeral by design.

## Consequences
- **Positive:** Single operational dependency for all edge-state. Atomic operations (`INCR`) guarantee correctness under concurrent load. Memory overhead is minimal (~10MB for the expected client volume).
- **Negative:** Redis becomes a critical path dependency — if it goes down, all authenticated requests fail. Mitigated by Docker's `restart: unless-stopped` policy.
