## Playbook 3: The Pydantic Data Contract

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
