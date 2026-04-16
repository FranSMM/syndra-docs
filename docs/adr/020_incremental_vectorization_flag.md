# ADR 020: Incremental Vectorization via is_vectorized Flag

**Status:** Accepted

## Context
During the pipeline flow, data is embedded into high-dimensional vectors and pushed to Qdrant. While Qdrant provides native idempotency through upserts (preventing duplicate entries by ID), generating vectors using the local SentenceTransformer model is highly CPU intensive. Pumping the entire historical dataset through the embedding engine on every run causes severe performance bottlenecks.

## Decision
An `is_vectorized` boolean state flag was introduced into the JSONB data structure of the Bronze layer (Raw Articles). 

## Reasoning
This flag allows the orchestration pipeline to implement a software-level pre-filter. Before passing texts to the computationally expensive NLP models, the pipeline queries Postgres to retrieve only the subset of documents where `is_vectorized` is false or missing. 

## Consequences
- Massive reduction in batch processing times and CPU load.
- Pipeline execution becomes strictly incremental, computing vectors only for novel data.
- Retains Qdrant's mathematical idempotency as a fallback safety layer.
