## Playbook 5: The Operations Hub (Makefile)

**Usage:** Centralizing complex Docker, Scrapy, and Python execution commands to reduce cognitive load.

```makefile
# ETL Pipeline Execution

crawl:
	docker compose exec backend bash -c "cd app/scraper && export PYTHONPATH=/code && scrapy crawl elpais_rss -O test_output.json"

load:
	docker compose exec backend python -m app.scraper.load_to_db

run-etl:
	docker compose exec backend python -m app.pipeline
```
