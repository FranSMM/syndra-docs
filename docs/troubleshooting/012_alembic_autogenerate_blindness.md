## Incident 012: Alembic Autogenerate Blindness (JSONB Indexes)

**Symptom:** Running `alembic revision --autogenerate` successfully detects new tables but fails to detect or create GIN indexes on specific nested JSONB paths (e.g., `payload -> 'financial_metadata' -> 'tickers'`).

**Root Cause:** SQLAlchemy's autogenerate plugin maps declarative models to standard SQL. However, it cannot reliably infer complex, dialect-specific Postgres statements like generalized inverted indexes on nested JSON keys.

**Resolution:**

* Never trust --autogenerate for performance tuning.
* Separate table creation from index creation to maintain atomic migrations.
* Generate an empty migration (alembic revision -m "add_gin_index") and explicitly inject raw SQL using op.execute("CREATE INDEX ix_name ON table USING GIN ((payload -> 'path'));").
