## ADR 015: Endpoint Consolidation (Accepted Technical Debt)

**Status:** Accepted

**Context:** The current `GET /api/v1/sentiment/{ticker}` endpoint computes the aggregated sentiment score AND returns the raw individual signals (articles) in a single responde payload.

**Decision:** Accept this unified endpint for this phase MVP. Enforced a hard `limit` parameter (max 100) via Pydantic to mitigate DoS risk.

**Rationale:** This accelerates the initial go-to-market. However, it is acknowledged as technical debt. In mature DaaS model, the aggregated oracle (score) and the raw feed (news) are distinct products with different pricing and rate limits. Next phase will split this into dedicated `/sentiment`and `/news`endpoints.
