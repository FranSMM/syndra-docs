## Incident 010: Silent JSONB Mutation in PostgreSQL

**Symptom:** The AI model executed inference correctly and assigned scores to the article's dictionary in Python, but after the `session.commit()`, the database still showed empty metadata fields.

**Root Cause:**  SQLAlchemy does not automatically track deep mutations within a `JSONB` object if the main dictionary's memory pointer does not change.

**Resolution Applied:**  Forced SQLAlchemy to mark the column as "dirty" (modified) by explicitly invoking `flag_modified(article, "payload")` before each commit.
