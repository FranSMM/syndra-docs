# ADR 042: Models Pinned in the Image, No Hub Access at Run Time

**Status:** Accepted
**Relates to:** [ADR 041](./041_etl_metrics_derived_from_prefect_db.md), [PLB-008](../engineering_playbooks/008_huggingface_model_management.md)

## Context

Benchmark 07, looking for why the ML stages do not scale with the number of articles, found that every run asked Hugging Face whether models already on disk had a new version. Following that thread exposed three problems with one cause: the models were not pinned to anything.

1. **Performance.** The Hub check cost ~3.5 s per run (0.92 s sentiment, 2.56 s indexing; median of 30 probes in the production scheduler), 16 % of a ~22 s ETL, for nothing.
2. **Run-time dependency.** If `huggingface.co` did not answer, the ETL and the API's first semantic search depended on a third party.
3. **Reproducibility, the most serious.** `ProsusAI/finbert` without a revision means "whatever is on main today". New upstream weights would reach production on the next load, changing sentiment with no deploy, no commit and no record. For a historical financial dataset that breaks the comparability of the series.

Also: MiniLM was not in the image at all. `/models_cache` is not a volume, so every new container downloaded it again on its first run (cache written 61 minutes after the 28/09/2026 deploy, at the first ETL run).

## Decision

Two parts that only work together:

- **Both models baked into the image, each pinned to a Hub commit:** FinBERT `4556d13`, MiniLM `1110a24`, the revisions production already had on `refs/main`.
- **`HF_HUB_OFFLINE=1` in the image:** no load reaches the network.

The revision lives in `ENV` variables in the Dockerfile that both the download and every load read. Pinning only the download would not be enough: the load would look for `main`, which does not exist in a cache stored by hash, and fail offline.

The build downloads the models and then loads them again with the network off. A missing file fails the build, not production.

## Alternatives rejected

- **Leave it as it was.** The three problems above.
- **A volume for `/models_cache`.** Survives deploys, but the model no longer ships with the image, still checks the Hub and is still unpinned.
- **Offline only in the scheduler (compose).** The API, same image, would keep checking and downloading MiniLM on its first search.
- **Pin the revision without going offline.** Fixes reproducibility but keeps paying for the check and depending on the Hub on every load.

## Consequences

- **Measured:** the Hub check drops to zero within its confidence interval, and the fixed cost per run falls 0.63 s in sentiment and 2.25 s in indexing, about 2.9 s per run (213 runs after the change). Runs with no articles, which load no model, did not change, as expected.
- **Sentiment unchanged:** on the 256 texts of benchmark 04, pinned and offline against the previous setup gave identical probabilities and labels. Both load the same `pytorch_model.bin`.
- **Updating a model becomes deliberate:** change the revision and rebuild (PLB-008). A new MiniLM revision changes the vector space, so Qdrant must be fully reindexed.
- The image grows by ~90 MB (MiniLM).
- Inference no longer depends on any third party at run time. The RSS sources remain external by nature.
