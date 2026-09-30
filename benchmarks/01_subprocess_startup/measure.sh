#!/usr/bin/env bash
# Experiment 01: startup cost of the extraction and load subprocesses.
# Read-only: imports and `scrapy list`, no network and no writes.
set -euo pipefail
cd "$(dirname "$0")"
source ../lib/common.sh

CONTAINER="${CONTAINER:-syndra_scheduler}"
REPS="${REPS:-30}"

mkdir -p results
STAMP="$(new_stamp)"
CSV="results/startup_${STAMP}.csv"
ENVIRONMENT="results/startup_${STAMP}_environment.txt"

write_environment_header "$ENVIRONMENT"
{
  echo "repetitions: $REPS"
  vps "
    echo image: \$(docker inspect -f '{{.Config.Image}}' $CONTAINER)
    echo cores: \$(nproc)
    echo memory_mb: \$(free -m | awk '/Mem:/{print \$2}')
    docker exec $CONTAINER python -c 'import sys, scrapy, sqlalchemy; print(\"python:\", sys.version.split()[0]); print(\"scrapy:\", scrapy.__version__); print(\"sqlalchemy:\", sqlalchemy.__version__)'
  "
} >> "$ENVIRONMENT"

echo "measurement,repetition,ms" > "$CSV"
vps "docker exec -i $CONTAINER python -" >> "$CSV" <<PY
import subprocess, time

REPS = $REPS
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
