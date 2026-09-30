# 🐳 Infrastructure & DevOps 

> **This directory contains all IaC (Infrastructure as Code), container configurations, and platform setups for the Syndra DaaS environment.**

---

## 🗺 Docker-First Topology

Syndra utilizes a strict Docker-First monorepo approach, containerizing all dependencies to ensure parity across development, staging, and production. The root `docker-compose.yml` spins up the complete platform ecosystem:

- **🕸️ api:** The FastAPI asynchronous backend serving financial data endpoints.
- **🐘 postgres:** The Relational Database (`Port 5432`). Stores raw financial text, metadata, and sentiment aggregations.
- **📐 qdrant:** The Vector Database (`Port 6333`). Stores document embeddings for semantic search and operational fast-retrieval.
- ** orchestrator:** `prefect-server` data pipeline orchestrator managing ETL scheduling and pipeline state.
- **⚡ redis:** High-speed caching layer for API responses and rate-limiting.

---

## 🧠 Local Edge Inference

To ensure strict data privacy and eliminate recurring cloud API costs, the system's NLP workload (sentiment analysis, ticker extraction via sentence-transformers/GGUF) is executed locally. 

The architecture is explicitly optimized to run efficiently on **WSL2 / Edge hardware**, processing batch inference directly against the containerized data nodes without requiring external REST calls to third-party LLM providers.

---

## 🗄 Volumes & Persistence

Local directory volumes inside `./data` are utilized for robust data persistence across container restarts:

```text
data/
├── postgres/          # Relational financial data storage
├── qdrant/            # Vector embeddings storage
└── grafana/           # Dashboard configurations (Future)
```

> ⚠️ **Warning:** Never delete these directories in production unless performing a deliberate hard wipe of the data tier.

---

## 🔒 Environment Variables

Refer to `.env.example` in the root directory. Critical variables include:

- `DATABASE_URL`
- `QDRANT_HOST`
- `API_KEY_SECRET`

---

## 📊 Monitoring

- **Grafana Dashboard:** `http://localhost:3000` *(Default credentials mapped in `.env`)*
- **Key Metrics to Track:**
  - API Latency (p95) for data clients
  - Local Vector/GGUF inference times & VRAM utilization
  - Prefect ETL pipeline success rates