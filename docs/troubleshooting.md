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
