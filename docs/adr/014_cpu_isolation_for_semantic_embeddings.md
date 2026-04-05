## ADR 014: CPU Isolation for Semantic Embeddings

**Status:** Accepted

**Context:** The hardware infrastructure utilizes a single Edge AI GPU (NVIDIA GTX 1650 Ti with 4GB VRAM). The FinBERT model already occupies a significant portion of this VRAM. Introducing the Qdrant embedding model (`all-MiniLM-L6-v2) to the GPU simultaneously triggers catastrophic OOM (Out-of-Memory) crashes.

**Decision:** Forced the initialization of `SentenceTransformer` to use `device='cpu'`.

**Rationale:** System stability takes avsolute precedence over marginal latency improvements. `all-MiniLM-L6-V2` is highly optimized (~80MB) and generates 384-dimensional embeddings efficiently on modern CPUs. Offloading it to the CPU acts as a physiscal sandbox, ensuring zero VRAM collisions with the primary sentiment inference engine.
