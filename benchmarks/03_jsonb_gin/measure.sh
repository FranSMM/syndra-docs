#!/usr/bin/env bash
# Experiment 03: which index the per-ticker API query needs, and from what volume.
# Runs on a local copy of production data in a throwaway Postgres. Production is
# only read, once, by pg_dump.
set -euo pipefail
cd "$(dirname "$0")"
source ../lib/common.sh

SIZES="${SIZES:-10000 25000 50000 all}"
REPS="${REPS:-30}"
REFRESH_DUMP="${REFRESH_DUMP:-0}"
DUMP_DIR="$BENCH_CACHE/03_jsonb_gin"
DUMP="$DUMP_DIR/articles_dump.sql.gz"
# Same image and digest as production, read from the compose file so the two
# cannot drift apart. Only `image:` lines count: comments mention old tags.
PG_IMAGE=$(sed -nE 's/^[[:space:]]*image:[[:space:]]*(postgres:[^[:space:]]+).*/\1/p' \
  "$REPO_ROOT/infra/docker-compose.prod.yml" | head -1)
CONTAINER="syndra_bench_pg_$$"

mkdir -p results "$DUMP_DIR"
STAMP="$(new_stamp)"
QUERIES_CSV="results/queries_${STAMP}.csv"
INDEXES_CSV="results/indexes_${STAMP}.csv"
ENVIRONMENT="results/queries_${STAMP}_environment.txt"

# The dump holds scraped article text, so it stays in the cache, outside the
# repository. It is reused until REFRESH_DUMP=1, so a session measures one snapshot.
if [ "$REFRESH_DUMP" = 1 ] || [ ! -s "$DUMP" ]; then
  echo "-> dumping articles and raw_articles from production (read-only)"
  vps "docker exec syndra_postgres sh -c 'pg_dump -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --no-owner --no-privileges -t articles -t raw_articles'" \
    | gzip > "$DUMP.tmp"
  mv "$DUMP.tmp" "$DUMP"
fi

trap 'docker rm -f "$CONTAINER" >/dev/null 2>&1' EXIT
# Two CPUs, like the VPS. Memory is left free, as it is for Postgres in production.
docker run -d --name "$CONTAINER" --cpus 2 \
  -e POSTGRES_PASSWORD=bench -e POSTGRES_DB=bench "$PG_IMAGE" >/dev/null
# Checked over TCP: during initialisation Postgres only listens on its socket,
# so a TCP answer means the final server is up, not the temporary one.
until docker exec "$CONTAINER" pg_isready -h 127.0.0.1 -U postgres -d bench >/dev/null 2>&1; do
  sleep 1
done
echo "-> restoring the dump"
gunzip -c "$DUMP" | docker exec -i "$CONTAINER" psql -X -q -v ON_ERROR_STOP=1 -U postgres -d bench >/dev/null

write_environment_header "$ENVIRONMENT"
{
  echo "postgres_image: $PG_IMAGE"
  echo "container_limits: --cpus 2"
  echo "dump_taken: $(date -r "$DUMP" -Iseconds)"
  echo "dump_sha256: $(sha256sum "$DUMP" | cut -d' ' -f1)"
  echo "sizes: $SIZES"
  echo "repetitions: $REPS"
  echo "# Production usage of the Bronze GIN index from ADR 012, since statistics were last reset:"
  vps_psql app -At <<'SQL'
SELECT 'production_ix_raw_articles_tickers_scans: ' || idx_scan FROM pg_stat_user_indexes WHERE indexrelname = 'ix_raw_articles_tickers';
SELECT 'production_stats_reset: ' || coalesce(stats_reset::text, 'never') FROM pg_stat_database WHERE datname = current_database();
SQL
} >> "$ENVIRONMENT"

python3 bench_indexes.py --container "$CONTAINER" --sizes "$SIZES" --reps "$REPS" \
  --queries-csv "$QUERIES_CSV" --indexes-csv "$INDEXES_CSV" --environment "$ENVIRONMENT"

echo "Data:        $QUERIES_CSV"
echo "Indexes:     $INDEXES_CSV"
echo "Environment: $ENVIRONMENT"
