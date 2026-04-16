# ADR 018: Selection of Hetzner for Production VPS Infrastructure

**Status:** Accepted

## Context
Deploying the Syndra Data Engine requires a reliable Virtual Private Server (VPS) that can comfortably host a heavy Docker-based stack including PostgreSQL, Qdrant, FastAPI, Prefect, and local PyTorch/transformers inference workloads. We evaluated typical shared hosting/entry-level VPS providers like Hostinger against infrastructure-focused providers like Hetzner.

## Decision
**Hetzner** (specifically the CPX line, e.g., CPX21) was selected for our production environment.

## Reasoning
1. **Target Audience and Capabilities:** Providers like Hostinger are primarily oriented towards shared web hosting and WordPress deployments, offering convenience for non-technical users but featuring limited native Docker support and constrained system access.
2. **Predictable Performance:** Hetzner provides robust, developer-first infrastructure with true Virtual Private Servers that offer consistent CPU and RAM performance, which is mandatory for running intensive NLP models locally.
3. **GDPR Native Compliance:** Operating out of German and Finnish datacenters ensures strict native adherence to GDPR, providing a strategic advantage for future B2B Enterprise offerings.
4. **Community Reputation:** Hetzner has a strong, proven track record within the data engineering and self-hosting communities, offering unmatched price-to-performance ratios for Linux workloads.

## Consequences
- Full control over the host OS for our infrastructure-as-code and container deployments.
- Guaranteed performance ceilings to execute local FinBERT and SentenceTransformer models continuously.
