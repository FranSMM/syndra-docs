> ⚠️ **Note:** The actual codebase for Syndra is currently kept in a **private monorepo** as it is in active development.
>
> This public repository serves as the **Engineering & Architecture Log**. Here you will find the system architecture, ADRs (Architecture Decision Records), and troubleshooting logs that demonstrate my system design and problem-solving skills.

# 🧠 Syndra - Financial self-hosted AI & DaaS Platform 📈

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)

> **B2B FinTech Data-as-a-Service (DaaS) Platform leveraging self-hosted AI, NLP, and robust Data Engineering for financial intelligence.**

Syndra extracts financial news, runs local NLP (sentence-transformers/GGUF models) to calculate sentiment and extract tickers, and serves the enriched data via a high-performance REST API. 

**Note: Syndra is strictly API-First. There is no GUI or frontend component.**

---

## ⚡ API Preview

Syndra serves actionable financial intelligence directly to your systems.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/v1/sentiment/AAPL" \
     -H "Accept: application/json"
```

**Response:**
```json
{
  "ticker": "AAPL",
  "sentiment_score": 0.82,
  "trend": "bullish",
  "recent_headlines": [
    "Apple unveils new AI features across product line",
    "Strong Q3 earnings reported for AAPL",
    "Analysts upgrade Apple target price"
  ]
}
```

---

## ✨ Core Features

- **Automated Data Pipelines:** Fault-tolerant financial news extraction via Prefect workflows.
- **Strict Data Contracts:** Pydantic validation ensuring pristine data quality and type safety.
- **Idempotent Ingestion:** Safe retry mechanisms preventing duplicate database entries via URL hashing.
- **Local AI Processing:** 100% private, on-device NLP inference for sentiment analysis and ticker extraction (Edge AI/sentence-transformers).
- **API-First Architecture:** High-performance, highly concurrent REST APIs designed for B2B integration.

---

## 🏗 System Architecture & Stack

The platform is designed as a modular, high-performance DaaS pipeline utilizing the following core stack:
- **Docker**
- **FastAPI**
- **PostgreSQL**
- **Prefect**
- **Qdrant**
- **Local GGUF/Transformer models**

### Pipeline Overview

1. **Data Engineering (ETL):** Extraction pipelines managed by `Prefect` loading raw financial text into a `PostgreSQL` foundation.
2. **MLOps (Batch Inference):** Local sequence models (`sentence-transformers` & `GGUF` architectures) extract financial tickers and compute robust sentiment scores.
3. **High-Performance Backend:** Async `FastAPI` serving strict data contracts, backed by `Qdrant` (Vector/Semantic data) & `PostgreSQL` (Relational data).

---

## 📂 Monorepo Structure

```text
syndra-data-engine/
├── backend/          # FastAPI application, strictly typed DTOs, routing
├── infra/            # Docker-First infrastructure configurations
├── docs/             # Architecture and platform documentation
├── docker-compose.yml# Main Docker infrastructure configuration
├── .env.example      # Global environment variables template
└── README.md         # This file
```

---

## 🚀 Quickstart (Docker-First)

The entire stack is containerized. **You MUST have Docker and Docker Compose V2 installed** on your host machine. 

### 1. Clone the repository
```bash
git clone https://github.com/FranSMM/syndra-data-engine.git
cd syndra-data-engine
```

### 2. Setup environment variables
Configure your local environment by copying the example file:
```bash
cp .env.example .env
```

### 3. Spin up the infrastructure
Run the stack in detached mode:
```bash
docker compose up -d
```

### 4. Run the ETL Pipeline
Extract, validate, and load financial intelligence into your PostgreSQL database asynchronously:
```bash
make run-etl
```

---

## 📚 Documentation
For detailed information on platform modules:
- [Backend Documentation](./backend/README.md)
- [Infrastructure Documentation](./infra/README.md)
- [Architecture Decision Records](./docs/arquitecture_decision_records.md)
- [Troubleshooting & Incidents](./docs/troubleshooting.md)
