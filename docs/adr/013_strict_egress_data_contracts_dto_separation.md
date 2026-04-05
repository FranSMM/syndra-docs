## ADR 013: Strict Egress Data Contracts (DTO Separation)

**Status:** Accepted

**Context:** FastAPI makes it easy to return SQLAlchemy ORM models or reuse input Pydantic schemas (e.g., `Screaped Article`) directly in the enpoint.

**Decision:** Created strictly isolated Egress DTOs (Data Transfer Objects) (`ArticleSignalDTO`, `TickerSentimentResponse`) in a dedicated `schemas/sentiment.py` module.

**Rationale:** In B2B Data-as-a-Service (DaaS), the API response shape is the actual product. Quantitative funds build hardcoded pipelines around this JSON structure. If we reuse internal schemas, a minor ETL tweak could inadvertenly leak metadata or break client integrations. Explicit DTOs guarantee that our external SLA remains immutable regardless of internal refactoring.
