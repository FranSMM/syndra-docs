# ADR 023: Keyword Payload Indexing for Pre-Filtering in Qdrant

**Status:** Accepted

## Context
The Data API serves contextual queries that mandate structured filtering alongside semantic similarity (e.g., "Retrieve only negatively-toned news regarding $AAPL"). If Vector Databases lack explicit categorical indexes, they default to calculating the cosine similarity mathematical operation across *all* stored vectors first, before discarding unmatching entities post-calculation.

## Decision
Explicit `KEYWORD` structured payload indexes were implemented within our Qdrant collection for critical filtering metadata—specifically the `ticker` and `sentiment_label` attributes. Note that while Qdrant does not expose traditional `GIN` indexes like Postgres, its inverted schema achieves the same structural purpose.

## Reasoning
Creating inverted string indexes enables **Pre-filtering**. Upon receiving a query, Qdrant can instantly isolate the specific subset of vectors that match the ticker/sentiment requirement prior to executing any AI search metric. Mathematical similarity is then calculated purely over this highly distilled subset.

## Consequences
- Considerably reduced semantic search latency, especially as the vector store scales to house hundreds of thousands of daily articles.
- Minor increase in memory and disk overhead within the Qdrant node to maintain the index tree structures.
