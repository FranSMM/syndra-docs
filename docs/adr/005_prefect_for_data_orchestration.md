## ADR 005: Prefect for Data Orchestration

**Context:** The ETL pipeline (Extract -> Validate -> Load) needed to be automated. Cron jobs lack observability, and Apache Airflow is too heavy (requires JVM/complex infrastructure) for an Edge AI/local architecture.

**Decision:** Adopt Prefect 3.0 as the orchestration engine, utilizing the `.serve()` daemon method for lightweight scheduling.

**Consequences:** Python-native DAG creation using `@task` and `@flow`. Built-in automatic retries for transient network failures.
