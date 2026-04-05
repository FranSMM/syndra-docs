## ADR 011: Isolated Inference Orchestration (Subprocess)

**Status:** Accepted

**Context:** Prefect orchestrates the tasks. If the ML module were imported directly into the DAG, the FinBERT model (~400MB) would reside in the RAM of the main Prefect process indefinitely (memory leak).

**Decision:** The inference script (`enrichment_sentiment.py`) was encapsulated and is called via `subprocess.run` from the Prefect DAG.

**Consequences:** When the inference batch finishes, the Python process dies and the Operating System (Linux) recovers 100% of the RAM/VRAM immediately, ensuring the long-term stability of the DaaS environment.
