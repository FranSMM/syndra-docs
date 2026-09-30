# 03 - GIN index on JSONB

**Question:** what does the GIN index on `raw_articles.payload` buy over a sequential scan, and from what volume on is it noticeable?

**Status:** pending. Follow the template of [01_subprocess_startup](../01_subprocess_startup/) and the rules in the [index](../README.md): measuring and analysing kept separate, 30 repetitions, the first one reported apart, a fixed seed, and raw data under `results/`.

**What to measure:** query time for containment queries on `payload` with and without the index, using `EXPLAIN (ANALYZE, BUFFERS)`, against a copy and never against production. Record table row count and index size in the environment file.
