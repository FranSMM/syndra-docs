## Incident 006: Prefect Ephemeral Server Timeout

**Symptom:** The Prefect ETL flow aborts at exactly 20 seconds with: `[Errno 111] Connection refused` / `Timed out while attempting to connect to ephemeral Prefect API server.`

**Root Cause:** When using `.serve()`, Prefect spins up a temporary SQLite server. In virtualized environments (Docker in WSL2), file system translation latency caused SQLite to take ~21 seconds to start, exceeding Prefect's hardcoded 20-second threshold.

**Resolution Applied:** Increased the ephemeral startup timeout tolerance via environment variables without altering core infrastructure.
```env
PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=120
```
