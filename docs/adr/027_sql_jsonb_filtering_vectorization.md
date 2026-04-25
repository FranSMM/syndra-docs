# ADR 027: SQL-Level JSONB Filtering for Vectorization Pipeline

**Status:** Accepted

## Context
The `backfill_vectors.py` script was loading ALL Silver Layer articles into Python memory via `.all()`, then filtering out already-vectorized articles in a Python list comprehension by checking `raw.payload.get("is_vectorized", False)`. This meant PostgreSQL returned thousands of rows (including already-processed ones) just for Python to discard them.

At current scale (~1,135 articles), memory impact was negligible (~5MB). However, this pattern would not survive growth: at 50,000 articles, ~250MB of RAM would be consumed by ORM objects destined to be discarded — wasteful in a container limited to 2.5GB that also hosts FinBERT and MiniLM models.

## Decision
Push the `is_vectorized` filter down to PostgreSQL using native JSONB operators (`payload['is_vectorized'].as_boolean()`), and replace the load-all-then-slice pattern with a `LIMIT`-based `while True` loop that processes fixed-size batches directly from the database.

## Alternatives Considered

| Alternative | Rejected Because |
|---|---|
| `yield_per()` server-side cursors | Has known caveats with `asyncpg` driver. Does not solve the root cause (loading vectorized rows). |
| Dedicated `is_vectorized` column on Bronze | Violates Medallion Architecture principle: Bronze columns are structural metadata only. The flag is operational state, not article data. Keeping it in JSONB is consistent with ADR-020. |

## Implementation
```python
# BEFORE: Load all, filter in Python
rows = result.all()
articles = [(a, r) for a, r in rows if not r.payload.get("is_vectorized", False)]

# AFTER: Filter in SQL, paginate with LIMIT
stmt = (
    select(Article, RawArticle)
    .join(...)
    .where(
        Article.sentiment_label.is_not(None),
        db_or(
            RawArticle.payload["is_vectorized"].as_boolean().is_(None),
            RawArticle.payload["is_vectorized"].as_boolean() == False,
        )
    )
    .limit(BATCH_SIZE)
)
```

## Consequences
- PostgreSQL returns only un-vectorized articles. Memory consumption is bounded to `BATCH_SIZE` (64) ORM objects per iteration regardless of total dataset size.
- Lazy loading of the embedding model is preserved: `SentenceTransformer` is only imported if the first batch returns rows.
- The `while True` + `LIMIT` pattern is self-terminating: once all articles are marked `is_vectorized=True`, the query returns empty and the loop breaks.
- Consistent with existing pagination pattern used in `enrich_sentiment.py` (which already uses `.limit(batch_size)` in a `while True` loop).
