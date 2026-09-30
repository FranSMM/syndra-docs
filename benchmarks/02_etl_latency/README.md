# 02 - ETL latency per stage

**Question:** how is end-to-end latency split across Extract, Load, sentiment and indexing, and how has it evolved?

**Status:** pending. Follow the template of [01_subprocess_startup](../01_subprocess_startup/) and the rules in the [index](../README.md): measuring and analysing kept separate, 30 repetitions, the first one reported apart, a fixed seed, and raw data under `results/`.

**What to measure:** the durations already recorded in `prefect_db` since April 2026 (ADR 041). No load is generated here: the history is queried and aggregated per stage and per week. The analysis has to separate the step caused by adding sources from day-to-day noise.
