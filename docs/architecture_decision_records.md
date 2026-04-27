# 🧠 Architecture Decision Records (ADRs)

> This document tracks the engineering decisions I made while developing Syndra.

| ID | Title | Status |
|----|--------|--------|
| [ADR-001](./adr/001_docker_first_infrastructure.md) | "Docker-First" Infrastructure | Accepted |
| [ADR-002](./adr/002_choosing_fastapi_over_flask_django.md) | Choosing FastAPI over Flask/Django | Accepted |
| [ADR-003](./adr/003_postgresql_as_the_primary_database.md) | PostgreSQL as the Primary Database | Accepted |
| [ADR-004](./adr/004_custom_scraping_scrapy_vs_third_party_news_apis.md) | Custom Scraping (Scrapy) vs. Third-Party News APIs | Accepted |
| [ADR-005](./adr/005_prefect_for_data_orchestration.md) | Prefect for Data Orchestration | Accepted |
| [ADR-006](./adr/006_asynchronous_database_operations_sqlalchemy_2_0.md) | Asynchronous Database Operations (SQLAlchemy 2.0) | Accepted |
| [ADR-007](./adr/007_pivot_from_dual_inference_to_single_inference_finbert.md) | Pivot from Dual Inference to Single Inference (FinBERT) | Accepted |
| [ADR-008](./adr/008_cuda_activation_for_finbert_inference.md) | CUDA Activation for FinBERT Inference | Accepted |
| [ADR-009](./adr/009_continuous_sentiment_calculation_quant_grade_score.md) | Continuous Sentiment Calculation (Quant-Grade Score) | Accepted |
| [ADR-010](./adr/010_native_vs_heuristic_truncation.md) | Native vs. Heuristic Truncation | Accepted |
| [ADR-011](./adr/011_isolated_inference_orchestration_subprocess.md) | Isolated Inference Orchestration (Subprocess) | Accepted |
| [ADR-012](./adr/012_gin_indexing_on_nested_jsonb_arrays.md) | GIN Indexing on Nested JSONB Arrays | Accepted |
| [ADR-013](./adr/013_strict_egress_data_contracts_dto_separation.md) | Strict Egress Data Contracts (DTO Separation) | Accepted |
| [ADR-014](./adr/014_cpu_isolation_for_semantic_embeddings.md) | CPU Isolation for Semantic Embeddings | Accepted |
| [ADR-015](./adr/015_endpoint_consolidation_accepted_technical_debt.md) | Endpoint Consolidation (Accepted Technical Debt) | Accepted |
| [ADR-016](./adr/016_iterative_batch_processing_for_ml_inference.md) | Iterative Batch Processing for ML Inference | Accepted |
| [ADR-017](./adr/017_qdrant_vs_pgvector.md) | Selection of Qdrant over pgvector for Vector Search | Accepted |
| [ADR-018](./adr/018_vps_provider_hetzner_selection.md) | Selection of Hetzner for Production VPS Infrastructure | Accepted |
| [ADR-019](./adr/019_api_and_scheduler_container_separation.md) | Architectural Separation of API and Scheduler Containers | Accepted |
| [ADR-020](./adr/020_incremental_vectorization_flag.md) | Incremental Vectorization via is_vectorized Flag | Accepted |
| [ADR-021](./adr/021_url_hashing_deduplication.md) | Hashing also Title instead just URL for Duplicate Prevention | To-Do |
| [ADR-022](./adr/022_immutable_gitops_infrastructure.md) | Transition to Immutable GitOps Infrastructure in Production | Accepted |
| [ADR-023](./adr/023_qdrant_payload_keyword_indexing.md) | Keyword Payload Indexing for Pre-Filtering in Qdrant | Accepted |
| [ADR-024](./adr/024_medallion_architecture_bronze_silver_separation.md) | Complete Medallion Architecture Separation (Bronze/Silver) | Accepted |
| [ADR-025](./adr/025_ticker_dictionary_enhancement.md) | Institutional Ticker Dictionary Enhancement | Accepted |
| [ADR-026](./adr/026_lazy_loading_ephemeral_ml_models.md) | Lazy Loading for Ephemeral ML Models | Accepted |
| [ADR-027](./adr/027_sql_jsonb_filtering_vectorization.md) | SQL-Level JSONB Filtering for Vectorization Pipeline | Accepted |
| [ADR-028](./adr/028_native_auth_cache_rate_limiting.md) | Native Authentication, Cache, and Rate Limiting (Zero Dependencies) | Accepted |
| [ADR-029](./adr/029_byos_flashtext_source_agnostic_ingestion.md) | BYOS (Bring Your Own Source) and FlashText for Source-Agnostic Ingestion | Accepted |
| [ADR-030](./adr/030_redis_unified_session_state_backend.md) | Redis as the Unified Session-State Backend | Accepted |
| [ADR-031](./adr/031_caddy_vs_nginx_vs_traefix.md) | Caddy vs Nginx vs Traefik for Reverse Proxy & SSL Management | Accepted |
| [ADR-032](./adr/032_per_client_response_cache_isolation.md) | Per-Client Response Cache Isolation | Accepted |
| [ADR-033](./adr/033_late_deduplication_serving_layer.md) | Late Deduplication in Serving Layer via SequenceMatcher | Accepted |