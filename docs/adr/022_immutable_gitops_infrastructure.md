# ADR 022: Transition to Immutable GitOps Infrastructure in Production

**Status:** Accepted

## Context
Initial production deployments maintained a tight coupling with the local development environment. The VPS hosted the full plaintext source code repository (`/backend`), relied on a local `Makefile`, and required an alias (`dcp`) to enforce production manifests. This architecture presented security risks (IP exposure), caused operational friction during container build cycles, and made the deployment non-disposable.

## Decision
Production deployments were fully migrated to a strict **Cloud Native / GitOps** model:
1. Eradication of Git source code and development tools from the VPS host file system.
2. The VPS execution environment is now governed entirely by three static files encapsulated in a single directory: `docker-compose.yml`, `.env`, and `postgres-init.sh`.
3. Updating the platform now occurs strictly via fetching Docker images (`docker compose pull` targeting `ghcr.io/fransmm/syndra-etl:latest`) without compiling source on-site.
4. Added the explicit `name: syndra-data-engine` directive to the top of the Compose file to safely anchor and persist historical database volumes across the architectural transition.

## Consequences
- **Positive:** Drastic reduction in disk usage and attack surface. The architecture is now scalable and easily automatable (e.g., via Ansible/Terraform/CI-CD).
- **Negative / Trade-off:** We forfeit the ability to apply ad-hoc, "hot fixes" directly on the server's codebase. All system modifications now strictly obligate a formal Git commit and CI/CD build run to arrive at production.
