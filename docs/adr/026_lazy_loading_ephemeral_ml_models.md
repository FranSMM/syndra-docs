# ADR 026: Lazy Loading for Ephemeral ML Models

**Status:** Accepted

## Context
The Syndra orchestrator architecture dispatches isolated text extraction, sentiment enrichment, and semantic vector indexing tasks via ephemeral background processes (e.g. `subprocess.run`). Originally, the heavy HuggingFace models (`ProsusAI/finbert` and `sentence-transformers/all-MiniLM-L6-v2`) were instantiated globally at the module level using a standard Python Singleton pattern.

This caused the OS process to unconditionally load over 1.5GB of model weighting into memory during every single scheduled pipeline run, halting pipeline execution by ~27 seconds per run, *even when the database queries revealed zero pending or new articles to process*.

## Decision
A strict "Lazy Loading" (Scale-to-Zero) pattern was implemented for all Heavy Machine Learning artifacts. The classes and their respective underlying PyTorch dependency graphs are now instantiated (or imported) *only* inside the execution block, *after* querying PostgreSQL to verify that there is indeed a batch of unprocessed data.

## Reasoning
While the deployment VPS runs 24/7 to host the FastAPI application, the ETL pipeline orchestrator fires periodically as cron-like batch jobs. Pre-loading multiple Gigabytes of NLP models unconditionally into memory starves the core `api` container, PostgreSQL page cache, and Qdrant in-memory payloads. 

By deferring initialization to the last possible millisecond inside the un-processed data conditional block, the pipeline completes its verification in under 2 seconds and achieves a ~0% memory footprint when there are no new RSS pulses.

## Consequences
- **Positive:** Massive memory and compute savings on the production VPS during idle ETL chron triggers.
- **Positive:** Background Pipeline total execution drops from ~30+ seconds to <2 seconds during dry runs.
- **Negative:** Slightly increased engineering overhead and violation of PEP-8 (which encourages placing all imports at the top of the file) by enforcing deferred, function-level imports for Python ML modules.
