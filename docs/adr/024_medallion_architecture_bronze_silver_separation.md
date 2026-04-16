# ADR 024: Complete Medallion Architecture Separation (Bronze/Silver)

**Status:** Accepted

## Context
Due to early architectural compromises, the analytical NLP pipelines (FinBERT) were directly mutating the raw ingestion layer (`RawArticle` - Bronze). The system bypassed the intermediate, heavily structured layer (`Article` - Silver). Therefore, incoming data was irreversibly overwritten with sentiment labels, breaking idempotency, whilst the API struggled performing complex operations directly atop an unstructured Bronze table.

## Decision
We strictly enforce Medallion Architecture boundary lines across the schema and Python modeling layers:
1. **Bronze (`RawArticle`) Isolation:** Now strictly reserved for raw internet data. Its fields are un-mutated post-creation, with exceptions limited purely to operational state tracking flags (e.g. `pending` vs `processed`).
2. **Silver (`Article`) Utilization:** Opened and structurally typed to house the curated outputs executed by the models (containing clean titles, publishing dates, inferred sentiments, and linked tickers).
3. **API Routing:** Consumer queries served exclusively from the Gold/Silver domains, never extracting upstream from Bronze.

## Reasoning
This prevents destructive edits on the primary facts. If we choose to upgrade our NLP model in the future, retaining the pure, unaltered `RawArticle` database permits us to effortlessly perform a retroactive re-evaluation without needing to re-scrape historical data.

## Consequences
- Improved data integrity.
- Required writing custom ETL migration scripts to rescue thousands of previously mutated Bronze records and transplant them correctly into the new Silver mappings.
