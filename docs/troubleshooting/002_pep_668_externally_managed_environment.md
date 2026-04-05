## Incident 002: PEP 668 `externally-managed-environment`

**Symptom:** Running `pip install -r requirements.txt` fails with error: `externally-managed-environment`, even when a virtual environment appears active.

**Root Cause:** Newer Linux distributions (Ubuntu 24.04+, Debian 12+) implemented PEP 668 to prevent `pip` from breaking the OS package manager (`apt`). The terminal was falling back to the global `pip` executable due to a corrupted or improperly activated `venv`.

**Resolution Applied:** Destroyed and rebuilt the virtual environment from scratch.
```bash
rm -rf venv/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
