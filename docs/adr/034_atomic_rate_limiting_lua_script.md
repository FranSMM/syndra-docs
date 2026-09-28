# ADR 034: Atomic Rate Limiting via Redis Lua Script

**Status:** Accepted
**Supersedes:** The rate limiting mechanism described in [ADR 028](./028_native_auth_cache_rate_limiting.md)

## Context

ADR 028 implemented rate limiting with the canonical Redis `INCR` + `EXPIRE` pattern:

```python
current_count = await redis_client.incr(rate_key)
if current_count == 1:
    await redis_client.expire(rate_key, RATE_LIMIT_WINDOW_SECONDS)
ttl = await redis_client.ttl(rate_key)
```

This has two defects that only became visible under review:

**1. The counter can be orphaned without a TTL.** `INCR` and `EXPIRE` are two separate round-trips. If the API process is killed, the container is rescheduled, or the Redis connection drops in the gap between them, the key is created but never given an expiry. Redis then keeps it forever. That client's counter never resets and every subsequent request returns HTTP 429: a permanent, silent lockout of a paying B2B client that survives API restarts because the bad state lives in Redis, not in the process. Recovery requires a manual `DEL`.

The exposure is small per request but not negligible: it is hit on the *first* request of every window, i.e. at least once per minute per active client.

**2. Three round-trips per authenticated request.** `INCR`, `EXPIRE` and `TTL` are issued sequentially. ADR 028 claimed a "single Redis round-trip for cached + authenticated requests"; the real cost on the cache-hit path was five (`GET auth` + three for the limiter + `GET response`).

## Decision

Move the entire counter-and-window operation into a Lua script executed by Redis:

```lua
local current = redis.call('INCR', KEYS[1])
local ttl = redis.call('TTL', KEYS[1])
if current == 1 or ttl < 0 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
    ttl = tonumber(ARGV[1])
end
return {current, ttl}
```

Redis executes Lua scripts atomically: no other command interleaves and no partial state is observable. The increment and the expiry either both happen or neither does.

The script is registered once at import time via `redis_client.register_script(...)`, which uses `EVALSHA` with an automatic `EVAL` fallback if the script is not yet in Redis's cache. No I/O happens at registration.

**Self-healing:** the `ttl < 0` branch re-arms the window on any key that lacks an expiry. This repairs keys already orphaned by the previous implementation without a migration or a manual flush, the first request from an affected client fixes it.

## Alternatives Considered

| Option | Verdict |
|--------|---------|
| `SET key 0 EX 60 NX` then `INCR` | Two round-trips, still non-atomic as a pair. Solves the orphan case but not the interleaving one. |
| Redis pipeline (`MULTI`/`EXEC`) | Atomic and one round-trip, but cannot branch on the result of `INCR` inside the transaction: the conditional `EXPIRE` is not expressible. |
| Third-party library (`slowapi`, `fastapi-limiter`) | Rejected for the reasons in ADR 028: dependency conflicts with the async Redis stack. |
| Sliding-window log (sorted set) | Genuinely more accurate than the fixed window, but O(log N) per request and unbounded memory per key. Not justified at 100 req/min. |

## Consequences

- **Positive:** The permanent-lockout failure mode is eliminated. Rate limiting drops from three round-trips to one, bringing the cache-hit path to three total (auth GET, limiter EVALSHA, response GET) and much closer to ADR 028's original claim.
- **Positive:** Existing orphaned keys repair themselves on next contact.
- **Negative:** The window remains a *fixed* window, not a true sliding one. A client can still send 100 requests at second 59 and 100 more at second 61. Accepted: the limit exists to prevent resource exhaustion, not to meter billing precisely.
- **Negative:** Rate limiting logic now lives partly in Lua, which is not covered by the Python test suite and cannot be exercised without a live Redis. Requires a smoke test against a running stack after any change.
