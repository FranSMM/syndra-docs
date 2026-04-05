## ADR 010: Native vs. Heuristic Truncation

**Status:** Accepted

**Context:** FinBERT has a strict limit of 512 tokens (BERT architecture). Initially, a heuristic truncation by words was implemented (`text.split()[:400]`), which is unsafe given that the WordPiece tokenizer splits long or technical words into multiple tokens. 

**Decision:** Truncation was delegated exclusively to `transformers` library (truncation=True, max_length=512).

**Consequences:** 100% fail-fast execution guaranteed. Elimination of the risk of `IndexError` exceptions in Pytorch tensors during mass inference.
