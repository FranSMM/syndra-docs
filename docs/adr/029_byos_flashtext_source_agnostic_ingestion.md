# ADR 029: BYOS (Bring Your Own Source) and FlashText for Source-Agnostic Ingestion

**Status:** Accepted

## Context
Two compounding problems degraded the pipeline's commercial viability:
1. **Source Rigidity:** The Scrapy module was hardcoded to a single RSS spider, creating a single point of failure and preventing multi-source ingestion.
2. **Ticker Blindness:** Approximately 73% of ingested articles lacked a mapped financial ticker, rendering the majority of the Silver layer data commercially useless for B2B consumers.

## Decision

### Source-Agnostic Ingestion (BYOS)
The Scrapy extraction layer was parametrized to consume a `feeds.json` configuration file. Each entry defines a source name and RSS URL. The pipeline orchestrator iterates over all configured feeds dynamically, making the ingestion layer entirely source-agnostic. Adding a new data source requires only appending a JSON entry — zero code changes.

### FlashText (Aho-Corasick) Ticker Extraction
Replaced the previous regex-based NER heuristic with the **FlashText** library, which implements the Aho-Corasick algorithm for multi-pattern string matching in `O(N)` time complexity (linear in text length, independent of dictionary size). The keyword processor is loaded as a **Singleton** at application startup, pre-populated with the full institutional ticker dictionary, and reused across all inference cycles.

## Consequences
- **Positive:** Ingestion is now fully decoupled from any specific data provider. Ticker extraction recovered ~85% of previously untagged historical data via backfill. Processing speed improved dramatically compared to the previous per-ticker regex approach.
- **Negative:** `feeds.json` currently lacks schema validation (potential future improvement: Pydantic model for feed entries). FlashText has limited support for fuzzy matching — exact string matches only.
