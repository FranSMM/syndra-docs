## Incident 005: Data Leak - Title missing from JSONB payload

**Symptom:** After a successful ETL run, the JSONB `payload` column in Postgres lacked the article title, despite Scrapy extracting it successfully.

**Root Cause:** Disconnect between Validation and Storage. The title was extracted as a first-class attribute in Pydantic but was ignored during SQLAlchemy model instantiation, which only saved the nested payload dictionary.

**Resolution Applied:** Explicitly injected the title attribute into the payload dictionary prior to database insertion.
```python
article_payload = data.get('payload', {})
article_payload['title'] = data.get('title')
db_article = RawArticle(..., payload=article_payload)
```
