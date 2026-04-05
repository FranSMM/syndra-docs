## ADR 006: Asynchronous Database Operations (SQLAlchemy 2.0)

**Context:** FastAPI is fully asynchronous. Scrapy operates on Twisted (an async network engine). To prevent bottlenecks, the database layer must also be asynchronous.

**Decision:** Utilize SQLAlchemy 2.0 with the asyncpg driver and `AsyncSession` for all database interactions.

**Consequences:** Prevents I/O blocking during massive database inserts. Requires careful execution isolation (using `subprocess` in Prefect) when orchestrating Scrapy and SQLAlchemy to prevent event-loop collisions (`ReactorNotRestartable` errors).
