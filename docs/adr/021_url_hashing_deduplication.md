# ADR 021: Hashing also Title instead just URL for Duplicate Prevention

**Status:** To-Do (low priority)

## Context
During the data ingestion process (scraping RSS feeds), ensuring idempotent extraction is critical to avoid polluting Postgres with duplicate articles. Historically, deduplication was performed by checking if an article's title already existed in the database.

## Decision
Transition to identifying and rejecting duplicates by hashing the source URL.

## Reasoning
Comparing long text strings line-by-line is significantly slower and computationally heavier than matching cryptographic hashes of a fixed length. URL hashing provides a highly reliable, deterministic unique identifier for scraped web routes.

## Consequences
- Faster ingestion and database insertion throughput.
- We deliberately accept a minimal technical debt: extreme edge cases where the exact same syndicated article gets published on distinct unique URLs will be ingested as separate documents. Empirical data shows this error occurrence is extremely negligible (~0.08% or 1 in 1,100 articles), making the performance gain drastically outweigh the duplicate penalty.
