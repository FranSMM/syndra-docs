## Incident 013: Broken Data Lineage: Missing source Field in Scrapy

**Symptom:** The API returns "source": "unknown" for correctly processed financial articles, degrading the quality of the B2B Data Contract.

**Root Cause:** The Scrapy spider (Extraction node) failed to inject the hardcoded source key into the ArticlePayload before the Postgres insertion. Because the Bronze Layer uses a flexible JSONB column, the database accepted the incomplete payload without raising an integrity error.

**Resolution:**

* DB Recovery (Backfill): Ran a raw SQL backfill query to patch existing data: `UPDATE raw_articles SET payload = jsonb_set(payload, '{source}', '"yahoo_finance"') WHERE payload->>'source' IS NULL;`.
* API Resilience: Implemented a fallback mechanism in the service layer using `getattr(article, 'source', None)` or `article.payload.get('source')`.
* ETL Enforcement (Pending): The spider's Pydantic schema must be updated to remove default values for critical fields, forcing a `ValidationError` (Fail-Fast) if the spider malfunctions.
