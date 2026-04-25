## Playbook 14: B2B Client Onboarding (API Key Provisioning)

**Objective:** Generate and deliver a secure API key for a new B2B client. Supports both permanent and trial (time-limited) keys.

### Procedure

**Step 1: Connect to the production VPS**
```bash
ssh $VPS_USER@$VPS_IP
cd ~/syndra-deploy
```

**Step 2: Execute the provisioning CLI**

**Permanent key** (default — no expiration):
```bash
docker compose exec api python -m app.scripts.provision_client "Client_Name"
```

**Trial key** (auto-expires after N days):
```bash
docker compose exec api python -m app.scripts.provision_client "Client_Name" --trial 7
```

> [!TIP]
> Common trial periods: `--trial 7` (1 week), `--trial 14` (2 weeks), `--trial 30` (1 month).

**Step 3: Capture the raw API key**

The script will output the raw API key exactly once:
```
 ✓ TRIAL API KEY CREATED SUCCESSFULLY
==========================================================
CLIENT:     Client_Name
RAW KEY:    syndra_XXXXXXXXXXXXXXXXXXXXXXXXXXX
TYPE:       TRIAL
EXPIRES AT: 2026-05-02 00:50 UTC
 -- This key will NOT be shown again. Store it securely. --
==========================================================
```

> [!CAUTION]
> The raw key is **never stored** in the database. Only its SHA-256 hash is persisted. If the key is lost, a new one must be generated.

**Step 4: Deliver the key to the client**

Transmit the raw API key through a **secure, single-use channel** (e.g., a self-destructing note via [PrivNote](https://privnote.com/) or equivalent). Never send API keys via email or unencrypted messaging.

### How Trial Key Expiration Works

1. The `expires_at` timestamp is stored in PostgreSQL alongside the key hash.
2. On each request, the auth middleware (`deps.py`) checks `expires_at` against the current UTC time.
3. If the key has expired:
   - The key is **auto-deactivated** (`is_active = False`) in the database.
   - The client receives HTTP 403: `"API Key has expired. Contact support to renew."`
4. Redis auth cache TTL is dynamically capped to the key's remaining lifetime, preventing stale cache hits past expiration.

### Client Usage Instructions
Provide the client with the following integration example:
```bash
curl -H "X-API-Key: syndra_aB3dE..." https://your-domain/api/v1/articles?ticker=AAPL
```

### Revoking Access
To manually deactivate a client's API key before expiration:
```bash
docker compose exec api python -c "
import asyncio
from app.db.session import AsyncSessionLocal
from app.models.api_key import APIKey
from sqlalchemy import select, update

async def revoke():
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(APIKey)
            .where(APIKey.client_name == 'Client_Name')
            .values(is_active=False)
        )
        await db.commit()
        print('Key revoked.')

asyncio.run(revoke())
"
```
