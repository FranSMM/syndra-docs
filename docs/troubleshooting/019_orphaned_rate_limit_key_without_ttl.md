## Incident 019: Orphaned Rate Limit Key Without TTL (Permanent Client Lockout)

**Symptom:** A client with a valid, active API key receives `HTTP 429 Rate limit exceeded` on every request, indefinitely. The lockout survives API container restarts. `X-RateLimit-Remaining` is stuck at `0` and `Retry-After` reports a nonsensical or absent value.

**Root Cause:** The rate limiter issued `INCR` and `EXPIRE` as two separate Redis commands:

```python
current_count = await redis_client.incr(rate_key)
if current_count == 1:
    await redis_client.expire(rate_key, RATE_LIMIT_WINDOW_SECONDS)
```

`INCR` creates the key with no expiry. If the process dies, the container is rescheduled, or the Redis connection drops in the window between the two commands, the key exists permanently with no TTL. Redis has no reason to ever remove it. The counter climbs past 100 and stays there.

Restarting the API does not help: the corrupted state lives in Redis, not in the application process. This is why the failure reads as "the client is banned" rather than "the API is broken".

**Diagnosis:** A TTL of `-1` on a rate limit key is the signature (`-1` means "exists, no expiry"; `-2` means "does not exist"):

```bash
docker compose exec redis redis-cli --scan --pattern 'ratelimit:*' | \
  while read k; do echo "$(docker compose exec -T redis redis-cli TTL "$k") $k"; done
```

**Immediate Recovery:** Delete the affected key. The next request recreates it cleanly.

```bash
docker compose exec redis redis-cli DEL "ratelimit:<sha256_of_api_key>"
```

**Permanent Resolution:** Replaced `INCR` + `EXPIRE` with a Lua script executed atomically by Redis ([ADR 034](../adr/034_atomic_rate_limiting_lua_script.md)). The increment and the expiry now happen inside a single atomic operation, so the intermediate state is unreachable. The script also re-arms the TTL on any key found with `ttl < 0`, meaning keys already orphaned by the old implementation repair themselves on the affected client's next request, no manual cleanup or Redis flush required.

**Verified 06/08/2026** against the local stack, by injecting the exact corrupted state rather than trusting the reasoning:

```
SET ratelimit:<hash> 500 ; PERSIST ratelimit:<hash>
  -> count=500  ttl=-1     (the orphan: counter over the limit, no expiry)
one authenticated request
  -> http=429   ttl=60     (re-armed)
```

The 429 on that request is correct: the counter was genuinely at 500. What matters is the TTL: the key now expires, so the client recovers within one window instead of being locked out permanently. On the same run, a first request on a clean key produced `count=1 ttl=60`, confirming the TTL is armed in the same atomic step as the increment.

**Architectural Lesson:** "Atomic" describes a single Redis command, not a sequence of them. Any multi-command invariant, here, *a counter must always carry an expiry*, needs `MULTI`/`EXEC` or Lua to hold under process failure. The dangerous property of this class of bug is that the corrupted state outlives the process that created it: the usual "restart it" reflex produces no change, which sends debugging in the wrong direction. Worth a Phase 6 Grafana alert: any `ratelimit:*` key with `TTL == -1` is by definition a bug.
