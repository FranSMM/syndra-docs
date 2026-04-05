## ADR 009: Continuous Sentiment Calculation (Quant-Grade Score)

**Status:** Accepted

**Context:** The default configuration of the HuggingFace pipeline (top_k=1) truncated the probability of the dominant class. This caused a statistical bug where all articles labeled as `neutral` received a forced score of `0.0`.

**Decision:** The analyzer was modified to extract the probabilities of all classes (top_k=None). The final score is calculated using the net impact formula: `Probability(Positive) - Probability(Negative)`.

**Consequences:** The database now stores a continous and real distribution of sentiment (e.g., a neutral article can have a score of `-0.0664` if it presents a slight pessimistic bias). This exponentially increases the algorithmic value of the data for B2B clients.
