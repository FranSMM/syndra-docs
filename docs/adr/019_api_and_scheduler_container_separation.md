# ADR 019: Architectural Separation of API and Scheduler Containers

**Status:** Accepted

## Context
Initially, the Docker compose architecture utilized a single monolithic container (`etl_worker` or `backend`) to handle both the FastAPI web server for responding to incoming HTTP requests and the background Prefect orchestration tasks (including heavy data transformation and ML inference).

## Decision
The monolithic component was split into two distinctly orchestrated containers: `api` and `scheduler`. Both containers share the exact same underlying Docker image (`syndra-etl`), but execute different entry commands. The `scheduler` overwrites the startup instruction to run `python -m app.pipeline`.

## Reasoning
1. **Fault Isolation:** Running heavy NLP inference and ETL pipelines creates spikes in memory consumption. When packaged together, an Out-Of-Memory (OOM) exception during data transformation would fatally crash the public-facing FastAPI server.
2. **Resource Allocation:** By separating the processes, we can use Docker Compose to apply strict, independent CPU and Memory limits (e.g., locking the API to 512MB RAM while allowing the Scheduler access to 2.5GB).

## Consequences
- Superior systemic stability and increased uptime for the B2B endpoints.
- Improved observability, allowing us to monitor logs and metrics for the web server and the ETL worker independently.
