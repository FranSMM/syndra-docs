## ADR 003: PostgreSQL as the Primary Database

**Context:** The initial prototype considered SQLite, but read/write concurrency requirements and the future need to store vector embeddings demanded a more robust solution.

**Decision:** Use PostgreSQL starting from Phase 0.

**Consequences:** Higher robustness and the possibility of utilizing extensions like pgvector if i decide not to use a dedicated Vector Store (e.g., Qdrant/Milvus) in Phase 2.
