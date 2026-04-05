## Incident 009: Lack of Hardware Acceleration (CUDA not detected)

**Symptom:**  Despite having a GTX 1650 Ti, the AI model initialization log indicated: `Loading ML model: ProsusAI/finbert on CPU...` and inference was extremely slow.

**Root Cause:** The Docker container in WSL2 lacked physical access to the host system's (Windows) GPU resources

**Resolution Applied:** 
1.  **Purge**: Removed the native Docker installation from the WSL2 terminal (`sudo apt-get purge docker-ce`).
2.  **Migration**: Installed Docker Desktop for Windows.
3.  **Integration**: Enabled WSL integration in Docker Desktop settings.
4.  **YAML Configuration**: Added the `deploy: resources: reservations: devices: capabilities: [gpu]` block to the backend service in `docker-compose.yml`.
5.  **Rebuild**: Forced an image rebuild to install the CUDA-compiled version of PyTorch.
