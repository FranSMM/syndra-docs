# 🛠️ Engineering Playbooks & Standards

> This document contains the reusable code snippets and engineering standards utilized across the Syndra monorepo.

---

## Snippet 1: "Fail-Fast" Configuration with Pydantic

**Usage:** Prevent the application from starting if critical environment variables are missing, avoiding runtime crashes deep in the stack.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Syndra"
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str
    POSTGRES_DB: str
    POSTGRES_PORT: str = "5432"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
```

---

## Snippet 2: Optimized Dockerfile for Python/FastAPI

**Usage:** Building lightweight, production-ready images while avoiding temporary cache files.

```dockerfile
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /code
COPY requirements.txt /code/
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY ./app /code/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

---

## Snippet 3: The Pydantic Data Contract

**Usage:** Enforcing strict data boundaries between the wild internet and our database. If a newspaper changes its format, the pipeline halts locally before corrupting PostgreSQL.

```python
from pydantic import BaseModel, HttpUrl, Field
from typing import Any, Dict

class ScrapedArticle(BaseModel):
    url: HttpUrl 
    source: str = Field(..., min_length=2, max_length=100)
    title: str = Field(..., min_length=5)
    payload: Dict[str, Any] = Field(default_factory=dict)
```

---

## Snippet 4: Idempotent Database Loading

**Usage:** Ensuring that running the ETL pipeline multiple times does not result in duplicate entries. Deduplication is delegated to PostgreSQL's B-Tree index by hashing the URL.

```python
import hashlib
from sqlalchemy.exc import IntegrityError

def generate_hash(url: str) -> str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()

# Inside the async load function...
for data in articles_data:
    article_hash = generate_hash(data['url'])
    db_article = RawArticle(..., content_hash=article_hash)
    session.add(db_article)
    
    try:
        await session.commit()
    except IntegrityError:
        # Fail-Safe: Hash collision detected by Postgres. 
        await session.rollback()
```

---

## Snippet 5: The Operations Hub (Makefile)

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
