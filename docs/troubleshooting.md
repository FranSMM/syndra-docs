# 🐛 Troubleshooting & Incident Log

> A transparent record of critical bugs, infrastructure issues, and their exact technical resolutions.

---

## Incident 001: Docker WSL `PermissionError 13`

**Symptom:** Executing `docker compose up` results in `Permission denied` when attempting to access `/var/run/docker.sock`.

**Root Cause:** The Linux/WSL user lacks default privileges to communicate with the Docker daemon.

**Resolution Applied:** Added the user to the Docker security group to avoid using `sudo`.
```bash
sudo usermod -aG docker $USER
newgrp docker
```

---

## Incident 002: PEP 668 `externally-managed-environment`

**Symptom:** Running `pip install -r requirements.txt` fails with error: `externally-managed-environment`, even when a virtual environment appears active.

**Root Cause:** Newer Linux distributions (Ubuntu 24.04+, Debian 12+) implemented PEP 668 to prevent `pip` from breaking the OS package manager (`apt`). The terminal was falling back to the global `pip` executable due to a corrupted or improperly activated `venv`.

**Resolution Applied:** Destroyed and rebuilt the virtual environment from scratch.
```bash
rm -rf venv/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Incident 003: Pydantic `ValidationError` during Alembic Generation

**Symptom:** Running `alembic revision --autogenerate` locally throws a validation error indicating missing `POSTGRES_USER` and `POSTGRES_PASSWORD` variables.

**Root Cause:** Environment Drift. The `.env` file lives in the monorepo root, but Alembic runs from the `backend/` subfolder. Pydantic failed to resolve the parent directory.

**Resolution Applied:** Executed Alembic strictly inside the Docker container, relying on Docker Compose to inject the environment variables natively.
```bash
docker compose exec backend alembic revision --autogenerate -m "migration"
```

---

## Incident 004: `ModuleNotFoundError` during ETL script execution

**Symptom:** Running `python app/scraper/load_to_db.py` inside Docker throws `ModuleNotFoundError: No module named 'app'`.

**Root Cause:** Executing a Python script via its direct file path alters `sys.path` to start at the script's specific directory, breaking absolute imports from the root package.

**Resolution Applied:** Executed the script using Python's native module flag (`-m`) from the root working directory (`/code`).
```bash
python -m app.scraper.load_to_db
```

---

## Incident 005: Data Leak - Title missing from JSONB payload

**Symptom:** After a successful ETL run, the JSONB `payload` column in Postgres lacked the article title, despite Scrapy extracting it successfully.

**Root Cause:** Disconnect between Validation and Storage. The title was extracted as a first-class attribute in Pydantic but was ignored during SQLAlchemy model instantiation, which only saved the nested payload dictionary.

**Resolution Applied:** Explicitly injected the title attribute into the payload dictionary prior to database insertion.
```python
article_payload = data.get('payload', {})
article_payload['title'] = data.get('title')
db_article = RawArticle(..., payload=article_payload)
```

---

## Incident 006: Prefect Ephemeral Server Timeout

**Symptom:** The Prefect ETL flow aborts at exactly 20 seconds with: `[Errno 111] Connection refused` / `Timed out while attempting to connect to ephemeral Prefect API server.`

**Root Cause:** When using `.serve()`, Prefect spins up a temporary SQLite server. In virtualized environments (Docker in WSL2), file system translation latency caused SQLite to take ~21 seconds to start, exceeding Prefect's hardcoded 20-second threshold.

**Resolution Applied:** Increased the ephemeral startup timeout tolerance via environment variables without altering core infrastructure.
```env
PREFECT_SERVER_EPHEMERAL_STARTUP_TIMEOUT_SECONDS=120
```

---

## Incident 007: Anti-Bot Blocking in RSS extraction (Yahoo Finance)

**Symptom:** The Scrapy pipeline executed successfully (Exit Code 0) but the log showed `scraped 0 items`. When running in debug mode, the following was observed: `DEBUG: Forbidden by robots.txt`

**Root Cause:** Scrapy obeys the target domains' `robots.txt` file by default. Yahoo Finance actively blocks generic scraping User-Agents

**Resolution Applied:** Modified the global Scrapy configuration file (settings.py):
1. `ROBOTSTXT_OBEY = False`
2. `USER_AGENT` was spoofed to mimic a standard Chrome browser on Windows.

---

## Incident 008: State Inconsistency in Ingestion State Machine (False Positives)

**Symptom:** After executing the orchestrator (`make run-etl`), the PostgreSQL insertion log showed success, but the AI enrichment script did not process any articles.

**Root Cause:** Misalignment in state contracts. The Data Loader saved new articles with `ingestion_state = 'loaded'`, while the ML node performed a query looking for articles in the `pending` state (`select(RawArticle).where(RawArticle.ingestion_state == 'pending')`).

**Resolution Applied:** Updated the SQLAlchemy query in enrich_sentiment.py to listen for the correct state (`loaded`). Additionally, the `batch_size` was increased to 200 to process the accumulated backlog.

---

## Incident 009: Lack of Hardware Acceleration (CUDA not detected)

**Symptom:**  Despite having a GTX 1650 Ti, the AI model initialization log indicated: `Loading ML model: ProsusAI/finbert on CPU...` and inference was extremely slow.


**Root Cause:** The Docker container in WSL2 lacked physical access to the host system's (Windows) GPU resources

**Resolution Applied:** 
1.  **Purge**: Removed the native Docker installation from the WSL2 terminal (`sudo apt-get purge docker-ce`).
2.  **Migration**: Installed Docker Desktop for Windows.
3.  **Integration**: Enabled WSL integration in Docker Desktop settings.
4.  **YAML Configuration**: Added the `deploy: resources: reservations: devices: capabilities: [gpu]` block to the backend service in `docker-compose.yml`.
5.  **Rebuild**: Forced an image rebuild to install the CUDA-compiled version of PyTorch.


---

## Incident 010: Silent JSONB Mutation in PostgreSQL

**Symptom:** The AI model executed inference correctly and assigned scores to the article's dictionary in Python, but after the `session.commit()`, the database still showed empty metadata fields.

**Root Cause:**  SQLAlchemy does not automatically track deep mutations within a `JSONB` object if the main dictionary's memory pointer does not change.

**Resolution Applied:**  Forced SQLAlchemy to mark the column as "dirty" (modified) by explicitly invoking `flag_modified(article, "payload")` before each commit.


---

## Incident 011: "UNEXPECTED: bert.embeddings.position_ids" Warning loading FinBERT

**Symptom:**  The model loading log throws a warning indicating that the loaded model's keys do not exactly match the expected architecture.

**Root Cause:** Evolution of the transformers library. FinBERT was trained on an older BERT version where position IDs were not explicitly exported in the tensors. Modern versions expect them.

**Resolution Applied:** No code change was required. The warning is purely informative; the library recalculates the missing tensors on the fly with perfect mathematical precision.
