## Incident 016: Prefect Scheduler Inactive on Ephemeral Server

**Symptom:** The hourly ETL pipeline silently stopped executing in production. Logs showed `Cannot schedule flows on an ephemeral server`. No cron triggers were fired despite correct deployment configuration.

**Root Cause:** In Prefect 3.x, the `Scheduler` service is a component of the **central API server** (`prefect server start`). When using `.serve()` with an ephemeral (in-process SQLite) server, the scheduler daemon is never instantiated. Cron-based deployments require the full Prefect API to be running as a persistent, dedicated process.

**Resolution:**
1. Added a dedicated `prefect_server` container to `docker-compose.prod.yml` running `prefect server start` with a PostgreSQL backend.
2. Configured the `scheduler` container to point its `PREFECT_API_URL` to the new server container.
3. Exposed the Prefect UI for local monitoring via SSH tunnel:
```bash
ssh -L 4200:127.0.0.1:4200 user@vps-ip
```
4. Verified scheduler activity by confirming flow run creation in the Prefect UI dashboard.

**Key Lesson:** Prefect 3.x `.serve()` is a development convenience only. Production cron scheduling **requires** `prefect server start` as a separate, long-lived process.
