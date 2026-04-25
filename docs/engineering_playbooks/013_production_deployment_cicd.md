## Playbook 13: Production Deployment (Local CI/CD)

**Objective:** Deploy code changes from the local development environment to the production VPS using the immutable GitOps workflow.

### Prerequisites
- All changes are committed and pushed to Git.
- Docker is logged into GHCR: `docker login ghcr.io`
- `.env` contains `VPS_USER`, `VPS_IP`, and `DEPLOY_DIR` variables.
- SSH key-based authentication is configured for the VPS.

### Procedure

**Step 1: Execute the deployment script**
```bash
./deploy.sh
```

The script automatically performs:
1. **Build:** Compiles `ghcr.io/fransmm/syndra-etl:latest` from `./backend`.
2. **Push:** Uploads the image to GitHub Container Registry.
3. **Sync:** Transfers `docker-compose.prod.yml` to the VPS via `scp`.
4. **Restart:** Pulls the new image and restarts containers remotely via SSH, preserving all data volumes.

**Step 2 (Conditional): Apply database migrations**

If the release includes model/schema changes (new tables, columns, indexes):
```bash
ssh $VPS_USER@$VPS_IP
cd $DEPLOY_DIR
docker compose exec api alembic upgrade head
```

### Rollback Procedure
If the deployment causes issues, revert to the previous image:
```bash
ssh $VPS_USER@$VPS_IP
cd $DEPLOY_DIR
docker compose pull  # Will pull :latest which is the broken one
# Instead, re-tag and push the previous known-good commit locally:
# git checkout <last-good-commit>
# ./deploy.sh
```

### Verification
- Check container health: `ssh $VPS_USER@$VPS_IP "cd $DEPLOY_DIR && docker compose ps"`
- Verify API response: `curl -s https://your-domain/api/v1/health`
- Monitor logs: `ssh $VPS_USER@$VPS_IP "cd $DEPLOY_DIR && docker compose logs -f --tail=50 api"`
