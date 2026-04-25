## Playbook 15: Redis Monitoring and Cache Management

**Objective:** Monitor Redis health, inspect cache state, and perform cache invalidation in the production environment.

### Connecting to Redis CLI
```bash
ssh $VPS_USER@$VPS_IP
cd ~/syndra-deploy
docker compose exec redis redis-cli
```

### Health Check
```redis
PING
# Expected: PONG

INFO memory
# Check used_memory_human for current consumption

DBSIZE
# Total number of keys in the database
```

### Inspecting Active State

**List all cached auth sessions:**
```redis
KEYS auth:*
```

**Check rate limit status for a specific client:**
```redis
GET ratelimit:<key_hash>
TTL ratelimit:<key_hash>
```

**List all cached API responses:**
```redis
KEYS cache:*
```

### Cache Invalidation

**Invalidate a specific client's cached responses (e.g., after data refresh):**
```bash
docker compose exec redis redis-cli --scan --pattern "cache:<client_hash>:*" | xargs docker compose exec -T redis redis-cli DEL
```

**Full cache flush (use with caution — clears auth cache too, forcing re-authentication):**
```redis
FLUSHDB
```

> [!WARNING]
> `FLUSHDB` will clear rate limit counters, auth cache, and response cache simultaneously. All active clients will need to re-authenticate on their next request. Use only during maintenance windows.

### Monitoring Real-Time Traffic
```redis
MONITOR
```
This streams every command hitting Redis in real-time. Useful for debugging cache hit/miss patterns. Press `Ctrl+C` to exit.
