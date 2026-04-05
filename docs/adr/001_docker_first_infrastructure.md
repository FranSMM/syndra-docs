## ADR 001: "Docker-First" Infrastructure

**Context:** i needed a development environment immune to the "it works on my machine" syndrome, ready to be deployed to cloud servers without refactoring.

**Decision:** Adopt containers (Docker and Docker Compose) from the very first commit for the entire tech stack (API, Database, and future Vector Store).

**Consequences (Positive):** 100% reproducible environment and instant onboarding for any machine.

**Consequences (Negative):** Steeper initial learning curve and permission management overhead in Linux/WSL environments.
