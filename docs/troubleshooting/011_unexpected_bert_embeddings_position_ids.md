## Incident 011: "UNEXPECTED: bert.embeddings.position_ids" Warning loading FinBERT

**Symptom:**  The model loading log throws a warning indicating that the loaded model's keys do not exactly match the expected architecture.

**Root Cause:** Evolution of the transformers library. FinBERT was trained on an older BERT version where position IDs were not explicitly exported in the tensors. Modern versions expect them.

**Resolution Applied:** No code change was required. The warning is purely informative; the library recalculates the missing tensors on the fly with perfect mathematical precision.
