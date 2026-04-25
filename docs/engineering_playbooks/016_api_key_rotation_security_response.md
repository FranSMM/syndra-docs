## Playbook 16: API Key Rotation and Security Incident Response

**Objective:** Rotate a compromised API key and ensure no unauthorized access persists.

### When to Use
- A client reports a leaked or compromised API key.
- Suspicious activity is detected in API logs (unusual request patterns, unknown IPs).
- Routine key rotation as part of security hygiene.

### Procedure

**Step 1: Immediately revoke the compromised key**
```bash
ssh $VPS_USER@$VPS_IP
cd ~/syndra-deploy
docker compose exec api python -c "
from app.db.session import SessionLocal
from app.models.api_key import APIKey
db = SessionLocal()
key = db.query(APIKey).filter(APIKey.client_name == 'Affected_Client').first()
key.is_active = False
db.commit()
print('Key revoked.')
"
```

**Step 2: Flush the client's auth cache in Redis**
```bash
docker compose exec redis redis-cli --scan --pattern "auth:*" | xargs docker compose exec -T redis redis-cli DEL
```

> [!IMPORTANT]
> This flushes ALL auth caches, not just the compromised client's. This is intentional — since we store hashes, we cannot identify which `auth:` key belongs to the compromised client without recomputing all hashes.

**Step 3: Provision a new key for the client**
```bash
docker compose exec api python -m app.scripts.provision_client "Client_Name"
```

**Step 4: Deliver the new key via secure channel**

Use a self-destructing note service (e.g., PrivNote). Confirm receipt with the client.

**Step 5: Audit trail**

Check recent request logs for unauthorized access during the exposure window:
```bash
docker compose logs api --since="2h" | grep "Affected_Client"
```
