#!/usr/bin/env bash
# Experiment 04: FinBERT time and memory, one text at a time versus in batches.
# Runs locally in the deployed ETL image, limited to the scheduler's two cores
# and 2.5 GiB. Production is only read, once, to sample the texts.
set -euo pipefail
cd "$(dirname "$0")"
source ../lib/common.sh

BATCH_SIZES="${BATCH_SIZES:-1 2 4 8 16 32 64}"
REPS="${REPS:-30}"
ARTICLES="${ARTICLES:-64}"
SAMPLE_SIZE=256
IMAGE="${IMAGE:-ghcr.io/fransmm/syndra-etl:$(deployed_etl_tag)}"
# Same limits as the scheduler container in infra/docker-compose.prod.yml.
CPUS="0-1"
MEMORY="2560m"
TEXTS="$BENCH_CACHE/04_inference_resources/texts.jsonl"

mkdir -p results "$(dirname "$TEXTS")"
STAMP="$(new_stamp)"
CSV="results/inference_${STAMP}.csv"
ENVIRONMENT="results/inference_${STAMP}_environment.txt"

# The text fed to FinBERT is the description, or the title when there is none,
# as in app/ml/enrich_sentiment.py. Scraped text stays in the cache, outside
# the repository; it is sampled once so every session classifies the same texts.
if [ ! -s "$TEXTS" ]; then
  echo "-> sampling $SAMPLE_SIZE texts from production (read-only)"
  vps_psql app -At > "$TEXTS" <<SQL
SELECT json_build_object('text', coalesce(nullif(payload->>'description', ''), payload->>'title'))
FROM raw_articles ORDER BY id DESC LIMIT $SAMPLE_SIZE;
SQL
fi

docker image inspect "$IMAGE" >/dev/null 2>&1 || docker pull -q "$IMAGE" >/dev/null

PROBE_LOG="$(mktemp)"
trap 'rm -f "$PROBE_LOG"' EXIT

# stderr carries the model's loading chatter, so it goes to a log that is only
# shown when a probe fails.
run_probe() {
  docker run --rm --network none --cpuset-cpus "$CPUS" --memory "$MEMORY" \
    -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e PYTHONPATH=/code \
    -v "$PWD/probe.py:/bench/probe.py:ro" -v "$TEXTS:/bench/texts.jsonl:ro" \
    "$IMAGE" python /bench/probe.py --texts /bench/texts.jsonl "$@" 2>"$PROBE_LOG" \
    || { tail -5 "$PROBE_LOG" >&2; return 1; }
}

write_environment_header "$ENVIRONMENT"
{
  echo "image: $IMAGE"
  echo "image_digest: $(docker image inspect -f '{{join .RepoDigests " "}}' "$IMAGE")"
  echo "container_limits: --cpuset-cpus $CPUS --memory $MEMORY"
  echo "host_cpu: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)"
  echo "texts_sha256: $(sha256sum "$TEXTS" | cut -d' ' -f1)"
  echo "articles_per_repetition: $ARTICLES"
  echo "repetitions: $REPS"
  echo "batch_sizes: $BATCH_SIZES"
  run_probe --describe
} >> "$ENVIRONMENT"

echo "mode,batch_size,rep,articles,wall_ms,cpu_ms,rss_mb,peak_rss_mb,load_ms,load_rss_mb" > "$CSV"

measure_one() {
  echo "-> $*"
  # A process killed for memory is a result, not a failure of the script.
  if ! run_probe "$@" --reps "$REPS" --articles "$ARTICLES" >> "$CSV"; then
    echo "failed: $* (exit status suggests the $MEMORY limit was hit)" | tee -a "$ENVIRONMENT"
  fi
}

measure_one --mode production
for size in $BATCH_SIZES; do
  measure_one --mode batched --batch-size "$size"
done

echo "Data:        $CSV"
echo "Environment: $ENVIRONMENT"
