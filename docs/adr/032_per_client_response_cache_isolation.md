# ADR 032: Per-Client Response Cache Isolation

**Status:** Accepted

## Context
The sentiment endpoint cached responses in Redis using a global key pattern (`sentiment:{ticker}:{limit}`), shared across all authenticated clients. While all clients currently query the same Silver layer and receive identical results, this pattern presented two risks:

1. **Future BYOS per-client isolation:** If Syndra evolves to support per-client feed configurations, a shared cache would serve Client B data that was computed from Client A's private data sources.
2. **Correctness:** The original cache key also lacked the `limit` query parameter, causing a request with `limit=5` to receive a cached response generated for `limit=20`.

## Decision
Cache keys are now scoped per-client using the authenticated `client_name`:

```
# Before (global, no limit)
sentiment:AAPL

# After (per-client, limit-aware)
sentiment:Goldman_Sachs:AAPL:20
```

## Trade-off Analysis

| Concern | Shared Cache | Per-Client Cache |
|---------|-------------|-----------------|
| Redis memory | 1 entry per ticker | N entries per ticker (N = active clients) |
| Cache hit rate | Higher (all clients share) | Lower (each client warms its own cache) |
| Data isolation | None | Full tenant isolation |
| BYOS per-client ready | Would leak data | Safe by design |

With the current client volume (<10 B2B clients), the memory and hit-rate penalties are negligible (~500KB worst case). The isolation guarantee outweighs the marginal performance cost.

## Consequences
- **Positive:** System is multi-tenant safe from day one. Zero risk of cross-client data leakage regardless of future architectural changes.
- **Negative:** Each new client starts with a cold cache. First request per ticker/limit combination incurs a PostgreSQL query. Mitigated by the 5-minute TTL — after the first request, subsequent ones are served from cache.
