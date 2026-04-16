# ADR 025: Institutional Ticker Dictionary Enhancement

**Status:** Accepted

## Context
A core capability of the pipeline is accurately associating unstructured news texts with the correct publicly traded entities (Stock Tickers). The original mapping logic relied on rudimentary heuristic dictionaries. 

## Decision
The underlying ticker dictionary and matching algorithms have been substantially improved, implementing a heavier regex-based Named Entity Recognition (NER) approach tailored specifically for financial corpora.

## Reasoning
Accurate association is critical for B2B financial services. Expanding the deterministic boundaries of the dictionary prevents false negatives during inference cycles and ensures the semantic vector payload correctly attaches robust metadata references.

## Consequences
- Superior extraction of financial entities yielding a much purer Silver data layer.
- Minor performance hit during the text processing string-matching phase, fully offset by shifting this operation downstream onto the isolated `scheduler` container.
