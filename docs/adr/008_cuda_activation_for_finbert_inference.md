## ADR 008: CUDA Activation for FinBERT Inference

**Status:** Accepted

**Context:** Phase 2 of the MLOps pipeline executed sentiment inference with `ProsusAI/finbert` on CPU, resulting in processing times of ~3.5 minutes for batches of 50 articles. The documented project architecture contemplates the use of the GTX 1650 Ti GPU for hardware acceleration.

**Decision:** Enable CUDA inside the backend Docker container by:
*   Adding a `deploy.resources.reservations.devices` block in docker-compose.yml
*   Installing PyTorch compiled for CUDA 12.1 (--index-url https://download.pytorch.org/whl/cu121) in Dockerfile
*   Using Docker Desktop as the container runtime (instead of native nvidia-container-toolkit on WSL2) to simplify the development environment setup

**Alternatives considered:**
*   Native nvidia-container-toolkit on WSL2: Discarded - requires manual installation of ~7GB of system-level dependencies unnecessary for inference workloads.
*   Running inference outside the container: Discarded - breaks the Docker-First philosophy of the project and introduces host-level dependency management.

**Consequences:**
*   Inference time reduced from ~3.5 minutes to ~70 seconds per batch of 50 articles (~3x speedup).
*   Log confirms hardware acceleration: `Loading ML model: ProsusAI/finbert on CUDA (GPU NVIDIA GeForce GTX 1650 Ti with Max-Q Design)`
*   Development environment is bound to Docker Desktop on Windows with WSL2 integration enabled.
