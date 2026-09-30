#!/usr/bin/env bash
# Experiment 01: startup cost of the extraction and load subprocesses.
# Read-only: imports and `scrapy list`, no network and no writes.
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ../..)"

# The target comes from the root .env, which is not in git: the VPS address is
# never written into a tracked file. To measure elsewhere, export HOST.
read_env() { grep -E "^$1=" "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"' \r"; }
HOST="${HOST:-$(read_env VPS_USER)@$(read_env VPS_IP)}"
if [[ ! "$HOST" =~ ^[^@]+@[^@]+$ ]]; then
  echo "VPS_USER or VPS_IP missing from $ROOT/.env, or export HOST=user@machine." >&2
  exit 1
fi

CONTAINER="${CONTAINER:-syndra_scheduler}"
REPS="${REPS:-30}"

mkdir -p results
STAMP="$(date +%Y%m%d_%H%M%S)"
CSV="results/startup_${STAMP}.csv"
ENVIRONMENT="results/startup_${STAMP}_environment.txt"

{
  echo "date: $(date -Iseconds)"
  echo "repo_commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

  # With uncommitted changes the commit above does not identify the measured code.
  # Record the Git revision and working-tree state to identify the code used
  # for this measurement. The commit alone is not enough when local changes
  # are uncommitted, so dirty_tree makes those changes explicit.
  echo "dirty_tree: $(test -n "$(git status --porcelain 2>/dev/null)" && echo yes || echo no)"

  echo "repetitions: ${REPS}"
  
  ssh "$HOST" "
    echo image: \$(docker inspect -f '{{.Config.Image}}' ${CONTAINER})
    echo cores: \$(nproc)
    echo memory_mb: \$(free -m | awk '/Mem:/{print \$2}')
    docker exec ${CONTAINER} python -c 'import sys, scrapy, sqlalchemy; print(\"python:\", sys.version.split()[0]); print(\"scrapy:\", scrapy.__version__); print(\"sqlalchemy:\", sqlalchemy.__version__)'
  "
} > "$ENVIRONMENT"

echo "measurement,repetition,ms" > "$CSV"
ssh "$HOST" "docker exec -i ${CONTAINER} python -" >> "$CSV" <<PY
import subprocess, time

REPS = ${REPS}
MEASUREMENTS = [
    ("python_empty",       ["python", "-c", "pass"],                          "/code"),
    ("import_scrapy",      ["python", "-c", "import scrapy"],                 "/code"),
    ("import_sqlalchemy",  ["python", "-c", "import sqlalchemy"],             "/code"),
    ("extraction_startup", ["scrapy", "list"],                                "/code/app/scraper"),
    ("load_startup",       ["python", "-c", "import app.scraper.load_to_db"], "/code"),
]

for name, command, workdir in MEASUREMENTS:
    for i in range(1, REPS + 1):
        t0 = time.perf_counter()
        subprocess.run(command, cwd=workdir, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{name},{i},{(time.perf_counter() - t0) * 1000:.1f}")
PY

echo "Data:        $CSV"
echo "Environment: $ENVIRONMENT"
