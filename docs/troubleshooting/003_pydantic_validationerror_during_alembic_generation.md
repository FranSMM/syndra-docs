## Incident 003: Pydantic `ValidationError` during Alembic Generation

**Symptom:** Running `alembic revision --autogenerate` locally throws a validation error indicating missing `POSTGRES_USER` and `POSTGRES_PASSWORD` variables.

**Root Cause:** Environment Drift. The `.env` file lives in the monorepo root, but Alembic runs from the `backend/` subfolder. Pydantic failed to resolve the parent directory.

**Resolution Applied:** Executed Alembic strictly inside the Docker container, relying on Docker Compose to inject the environment variables natively.
```bash
docker compose exec backend alembic revision --autogenerate -m "migration"
```
