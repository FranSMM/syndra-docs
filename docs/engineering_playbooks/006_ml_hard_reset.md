## Playbook 6: ML Hard Reset (Full Signal Re-evaluation or Cleansing)

If a massive failure in the inference logic is discovered (e.g., a bug in the score calculation) and it is necessary to re-evaluate all historical articles with the new logic, follow this procedure:

1. Connect to the Bronze Database:

```bash
docker compose exec postgres psql -U syndra_user -d syndra_db
```

2. Reset the State Machine:

```sql
-- Reverts all processed articles to the loaded state so the ML node picks them up again.
UPDATE raw_articles SET ingestion_state = 'loaded' WHERE ingestion_state = 'processed';
```

3. Partial JSONB Cleansing (Optional):
If the nested structure was corrupted, you can purge the financial_metadata node while keeping the original text intact:

```sql
UPDATE raw_articles SET payload = payload - 'financial_metadata';
```

4. Re-run the Pipeline:

```bash
make run-etl
```
