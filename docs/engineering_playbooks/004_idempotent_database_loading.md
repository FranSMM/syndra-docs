## Playbook 4: Idempotent Database Loading

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
