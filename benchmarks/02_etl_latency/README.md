# 02 - ETL latency per stage

**Question:** how is end-to-end latency split across Extract, Load, sentiment and indexing, how has it evolved, and how much of each stage's cost depends on the number of feeds?

**Why no load is generated:** Prefect records the duration of every task run in `prefect_db`, and it has done so since April 2026. This experiment is observational: it exports that history instead of reproducing it, so it measures the real pipeline under its real schedule, and it can be repeated at any time without touching production beyond one read-only query.

**What is measured:** `total_run_time` of every task run and flow run, the same field the `syndra_etl_*` metrics use (ADR 041), with Prefect's hash suffix removed from stage names. Each flow run is tagged with the number of feeds it processed, read from its `BYOS: N active feed(s)` log line. The query runs in a session forced read-only.

**Run** (from WSL, with SSH access to the VPS):

    ./measure.sh
    python3 analyze.py results/etl_YYYYMMDD_HHMMSS.csv > results/etl_YYYYMMDD_HHMMSS_summary.csv

**Statistics:** medians rather than means, because a single network retry inside Extract can last tens of seconds and would move a mean without being representative. Each median carries a 95 % bootstrap confidence interval (10,000 resamples, seed 2026). The `feeds_difference` rows give the change in median between the largest and smallest feed count, with its own bootstrap interval: if the interval excludes zero, the step is not noise. Dividing that difference by the change in feed count gives the cost per feed.

**Limits:** it is observational, so a difference between feed counts could also come from anything else that changed at the same time; the weekly view is there to check that the change is a single step on the day the feeds were added and not a drift. Runs whose logs do not record a feed count are left out of the `feeds` view but kept in the `weekly` one. The 30-repetition rule of the index does not apply here: every recorded run is used.
