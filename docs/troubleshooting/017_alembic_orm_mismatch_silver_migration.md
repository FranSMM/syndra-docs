## Incident 017: Alembic ORM Mismatch During Silver Layer Migration

**Symptom:** Running `alembic revision --autogenerate` to generate the `Article` (Silver layer) table migration produced type errors. The generated migration contained `UUID` column types that conflicted with the intended `Integer` primary key. Subsequent `alembic upgrade head` failed with schema mismatch errors.

**Root Cause:** A two-fold desynchronization:
1. **Ghost Migrations:** The local `alembic_version` table referenced migration revisions that no longer existed in the `versions/` directory (deleted during earlier refactors), causing Alembic to enter an inconsistent state.
2. **SQLAlchemy 2.0 Typing:** The `Article` model was initially defined using legacy SQLAlchemy 1.x `Column()` syntax. SQLAlchemy 2.0's `--autogenerate` expected `Mapped[int]` / `mapped_column()` annotations, leading to incorrect type inference for the primary key and foreign key relationships.

**Resolution:**
1. Corrected the `Article` model to use SQLAlchemy 2.0 declarative syntax:
```python
class Article(Base):
    __tablename__ = "articles"
    id: Mapped[int] = mapped_column(primary_key=True)
    raw_article_id: Mapped[int] = mapped_column(ForeignKey("raw_articles.id"), unique=True)
    # ...
```
2. Reset the local migration state by manually updating the `alembic_version` table to match the last known-good revision:
```sql
UPDATE alembic_version SET version_num = '<last_good_revision>';
```
3. Generated a clean migration from the corrected baseline and verified with `alembic upgrade head`.

**Key Lesson:** Never delete migration files without also resetting `alembic_version`. Always use SQLAlchemy 2.0 `Mapped` types to prevent autogenerate inference errors.
