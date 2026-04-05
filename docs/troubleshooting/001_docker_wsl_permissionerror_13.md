## Incident 001: Docker WSL `PermissionError 13`

**Symptom:** Executing `docker compose up` results in `Permission denied` when attempting to access `/var/run/docker.sock`.

**Root Cause:** The Linux/WSL user lacks default privileges to communicate with the Docker daemon.

**Resolution Applied:** Added the user to the Docker security group to avoid using `sudo`.
```bash
sudo usermod -aG docker $USER
newgrp docker
```
