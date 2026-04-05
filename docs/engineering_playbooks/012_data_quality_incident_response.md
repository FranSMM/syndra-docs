## Playbook 12: Data Quality & Incident Response

* **The "Silent Failure" Doctrine:** Errors that crash the application trigger immediate logs. Errors that skip data corrupt the product silently.

* **Monitoring the Backlog:** The health of the ETL pipeline is measured by the size of the pending queue. If `SELECT COUNT(*) FROM raw_articles WHERE ingestion_state = 'pending'` is growing week-over-week, the ML inference layer is failing to keep up with the extraction layer.

* **Fail-Fast Ingestion:** Scrapy spiders must use strict Pydantic models without default values for critical fields like source or published_at. It is better to reject a scraped article and log a warning than to pollute the Bronze Layer with nulls.
