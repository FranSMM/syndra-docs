## Playbook 11: End-to-End ETL Execution (Prefect)

* The entire data pipeline is automated and isolated to prevent memory fragmentation and "Memory Leaks" common in ML models running within long-lived orchestrator processes.

* **Architectural Flow:** Extract (Scrapy) -> Load (Postgres) -> Enrich (FinBERT via Subprocess) -> Vectorize (MiniLM via Subprocess).

* **Subprocess Pattern:** Wrapping ML inference in `subprocess.run` guarantees that when the script finishes, the Operating System forcefully reclaims 100% of the VRAM/RAM, keeping the orchestrator lightweight.

* **Execution:**

```bash
make run-etl
```

*(In production, this is handled by Prefect's CRON scheduler via `etl_flow.serve()` running nightly.)*
