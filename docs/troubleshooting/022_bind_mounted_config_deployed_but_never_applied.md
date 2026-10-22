## Incident 022: Bind-Mounted Config Deployed but Never Applied (Public `/metrics`)

**Symptom:** A `respond 403` block for `/metrics` was added to `infra/Caddyfile` to keep the Prometheus scrape endpoint off the public internet. The change passed `caddy validate`, was copied to the VPS by `deploy.sh`, and the deploy finished green. `https://api.syndradata.com/metrics` still answered **HTTP 200 with 8899 bytes** — every route name, its latency histogram, and the size of the corpus, served to anyone who asked. The Caddyfile on the VPS contained the block. Caddy was simply not enforcing it.

**Root Cause:** Caddy reads its configuration from a bind mount (`./Caddyfile:/etc/caddy/Caddyfile`), and a bind mount is invisible to `docker compose up -d`. Compose recreates a container when its *definition* changes — image, command, environment, ports, mounts. The bytes behind a mount are not part of that definition, so overwriting the file changes nothing Compose can detect. `docker ps` confirmed it plainly: every other container had just been recreated, while `syndra_caddy` read `Up 3 days`. It was still serving the config it parsed at boot, three days and several deploys earlier.

Nothing in the pipeline was broken. `caddy validate` did its job — it validates syntax, and the syntax was fine. `scp` did its job. `docker compose up -d` did its job. The defect was the unstated assumption joining them: that copying a configuration file is the same as applying it.

The same trap applied to `infra/prometheus.yml`, which had just been introduced with the same mount pattern. It went unnoticed only because the Prometheus container was brand new on that deploy and therefore read its config once, by accident of timing.

**Resolution:** `deploy.sh` now applies the configs it ships, rather than assuming a restart elsewhere will pick them up.

1. **Caddy is reloaded on every deploy.** `caddy reload` swaps the configuration without dropping connections, so it is cheap enough to run unconditionally — and unconditional is the point. A reload gated on "did the file change?" reintroduces a way for the file and the running config to diverge.
2. **A failed reload aborts the deploy.** Previously the only outcome worse than a broken config was a broken config reported as a success. If the reload fails, the script exits non-zero and says explicitly that Caddy is still serving the previous configuration.
3. **Prometheus is restarted only when `prometheus.yml` actually changed**, compared by checksum against the remote copy *before* the `scp` overwrites it. Prometheus has no graceful reload without `--web.enable-lifecycle`, and adding a mutating admin endpoint for a file that changes twice a year is a bad trade. A restart costs a few missed scrapes and no data: the TSDB lives on a volume and the WAL survives.

**Verification:**

```bash
# From outside the VPS, which is the only vantage point that proves anything.
curl -s -o /dev/null -w '%{http_code}\n' https://api.syndradata.com/metrics    # 403
curl -s -o /dev/null -w '%{http_code}\n' https://api.syndradata.com/metrics/   # 403
curl -s -o /dev/null -w '%{http_code}\n' https://api.syndradata.com/health     # 200

# The reverse proxy must still work: this 403 is the API's own auth rejection,
# not Caddy's block. A 403 with an empty body would mean the handle blocks are
# swallowing the whole vhost.
curl -s https://api.syndradata.com/api/v1/sentiment/AAPL                       # {"detail":"..."}

# And the scrape path, which never passes through Caddy, must be unaffected.
docker exec syndra_prometheus wget -qO- \
  'http://localhost:9090/api/v1/query?query=up'                                # up == 1
```

**Architectural Lesson:** A validation step proves the artefact is well-formed, never that it is in effect. Those are different claims, and only the second one is what anyone actually wanted. The deploy verified the Caddyfile could be parsed and then never asked whether anything had parsed it.

The general shape: when configuration reaches a process through a path the orchestrator does not model — a bind mount, a file fetched at boot, an environment read once — the deploy owns the job of telling that process to re-read it. Nothing else will.

The corollary is about how this was caught. It was not caught by the deploy, by the validation, or by reading the diff, because all three were correct. It was caught because the plan for the phase phrased its step as *"block `/metrics` — **verify the block from outside, do not assume it**"* rather than *"block `/metrics`"*. Writing the check into the task description is what turned a silent exposure into a ten-minute fix. This is the fourth incident in the same family as INC-020 (an idempotent initializer nothing called) and the inert `STOP_ALIASES` in the ticker extractor: code that exists, reads correctly, and does nothing.
