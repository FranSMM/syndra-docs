## ADR 007: Pivot from Dual Inference to Single Inference (FinBERT)

**Status:** Accepted

**Context:** Initially, the architectural design for Phase 2 contemplated loading two local NLP models simultaneously: `ProsusAI/finbert` (for sentiment classification) and `all-MiniLM-L6-v2` alongside Qdrant (for vector embeddings and semantic search). This would have required significant GPU resources and complex orchestration.

**Decision:** It was decided to pause the deployment of Qdrant and the embeddings model in favor of an isolated execution of FinBERT.

**Consequences:**
*   **Positive:** Absolute prevention of Out of Memory (OOM) crashes on the Edge hardware (GTX 1650 Ti / 4 GB VRAM). Direct alignment with the business model (prioritizing the extraction of "Alpha" signal over indexing).    
*   **Negative:** Semantic similarity search is postponed to Phase 3 or 4.
