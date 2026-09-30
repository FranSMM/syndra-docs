# 03 - Indexes for the per-ticker query

**Question:** which index does the query behind `/api/v1/sentiment/{ticker}` need, from what table size does it matter, and is the GIN index on `raw_articles.payload` from ADR 012 still earning its place?

**Why the question changed:** ADR 012 put a GIN index on `payload -> 'financial_metadata' -> 'tickers'` in Bronze. Since the Silver layer, the API reads `articles.tickers` instead, and `pg_stat_user_indexes` in production shows the Bronze index with no scans at all. The query that does run is `'NVDA' = ANY(a.tickers) ORDER BY a.published_at DESC NULLS LAST LIMIT 40` (`app/services/sentiment_service.py`), and `articles.tickers` has no index. The environment file records the production scan count, so that part of the answer comes with each run.

**Variants:**

| Variant | Indexes added | Query |
|---|---|---|
| `baseline` | none: the production schema | as production, `= ANY` |
| `gin` | GIN on `tickers` | rewritten as `tickers @> ARRAY[ticker]`, since `= ANY` cannot use GIN |
| `order_index` | B-tree on `published_at DESC NULLS LAST` | as production |
| `gin_and_order` | both | rewritten, and the planner chooses |

The existing index on `published_at` is ascending with nulls last, which does not match the query's order, so it cannot feed the `LIMIT` directly: that is what `order_index` tests. Before timing, every variant must return exactly the rows production returns (compared as the ordered list of `published_at`, since ties may come back in any order), or the run stops.

**Tickers:** three per table size, chosen from the data: the most covered, a typical one with enough articles to fill the `LIMIT`, and the rarest. An ordered scan stops early for a common ticker and has to read everything for a rare one, so the answer depends on which kind is asked for.

**Sizes:** copies of `articles` with the first 10,000, 25,000 and 50,000 rows by id, and the whole table. The first N rows by id are the table as it was when it had N rows.

**Environment:** a local, throwaway Postgres with the same image and digest as production (read from `infra/docker-compose.prod.yml`), limited to 2 CPUs like the VPS, restored from a `pg_dump` of `articles` and `raw_articles`. Production is only read, by that dump. The dump holds scraped article text, so it lives in `~/.cache/syndra-bench/`, never in the repository; its date and SHA-256 go into the environment file. Absolute times depend on the laptop's CPU; the comparison between variants is what carries over to the VPS.

**Run** (from WSL, with Docker and SSH access to the VPS):

    ./measure.sh
    python3 analyze.py results/queries_YYYYMMDD_HHMMSS.csv > results/queries_YYYYMMDD_HHMMSS_summary.csv

`REFRESH_DUMP=1` takes a new dump; otherwise the cached one is reused so several sessions measure the same snapshot. `results/indexes_*.csv` holds each index's build time and size (one build per variant and size, so treat build times as indicative).

**Statistics:** `EXPLAIN (ANALYZE, BUFFERS)` execution time, 30 repetitions per size, variant and ticker, the first reported apart because it reads from disk. Median with a 95 % bootstrap confidence interval (10,000 resamples, seed 2026), nearest-rank p95, the speed-up over `baseline` for the same size and ticker, and the plan's access paths so the change of strategy is visible, not only its effect.
