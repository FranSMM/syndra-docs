## Playbook 10: Disaster Recovery: Vector Database (Qdrant)

If the Qdrant Docker volume is accidentally deleted, corrupted, or we decide to swap the embedding model (e.g., moving from MiniLM to OpenAI/Cohere), the vector database can be regenerated entirely and safely from the Postgres Silver Layer.

* **Idempotent Design:** The backfill script uses deterministic hashing (uuid.uuid5) based on the PostgreSQL primary key (id). Executing it multiple times will safely overwrite existing vectors without creating ghost duplicates.

* **Execution Command:**

```bash
docker compose exec backend python -m app.pipeline.backfill_vectors
```

* **Memory Protection:** The script is hardcoded to process data in chunks of 64 articles. Do not increase this batch size without monitoring system RAM, as text encoding scales linearly in memory consumption.
