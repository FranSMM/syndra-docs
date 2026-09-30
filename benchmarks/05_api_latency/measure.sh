#!/usr/bin/env bash
# Experiment 05: API latency at the load of a single client.
# Runs against production at 0.4 requests/s, well under the 100/min per-key limit.
set -euo pipefail
cd "$(dirname "$0")"
source ../lib/common.sh

# A dedicated test key, never the demo one. Kept in the git-ignored root .env,
# or exported for a single session.
SYNDRA_BENCH_KEY="${SYNDRA_BENCH_KEY:-$(read_env SYNDRA_BENCH_KEY)}"
: "${SYNDRA_BENCH_KEY:?set SYNDRA_BENCH_KEY in the root .env (see README)}"
BASE="${BASE:-https://api.syndradata.com}"
# 0.4/s: the 141 tickers take 352 s to cycle, longer than the 300 s cache TTL,
# so every cold request really misses the cache.
RATE="${RATE:-2/5s}"
DURATION="${DURATION:-10m}"
REPS="${REPS:-3}"
SCENARIOS="${SCENARIOS:-sentiment_warm sentiment_cold search_warm search_cold}"
# Longer than both cache TTLs, so no run inherits the previous one's cache.
PAUSE_SECONDS="${PAUSE_SECONDS:-310}"
ETL_GUARD="${ETL_GUARD:-1}"
CLIENT_LABEL="${CLIENT_LABEL:-laptop-wsl}"

VEGETA="$(ensure_vegeta)"

duration_minutes() {
  case "$1" in
    *m) echo "${1%m}" ;;
    *s) echo $(( (${1%s} + 59) / 60 )) ;;
    *)  echo 60 ;;
  esac
}
DURATION_MIN=$(duration_minutes "$DURATION")

# The ETL runs at :58 every hour and competes for the same two cores. A run must
# fit between :05 and :55, or its latencies measure the pipeline, not the API.
wait_for_etl_free_window() {
  [ "$ETL_GUARD" = 1 ] || return 0
  if [ "$DURATION_MIN" -gt 50 ]; then
    echo "DURATION must be 50m or less to fit between ETL runs" >&2
    exit 1
  fi
  local minute
  while :; do
    minute=$((10#$(date +%M)))
    if [ "$minute" -ge 5 ] && [ $((minute + DURATION_MIN)) -le 55 ]; then
      return 0
    fi
    sleep 20
  done
}

mkdir -p results
STAMP="$(new_stamp)"
CSV="results/latency_${STAMP}.csv"
ENVIRONMENT="results/latency_${STAMP}_environment.txt"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

write_environment_header "$ENVIRONMENT"
{
  echo "deployed_etl_tag: $(deployed_etl_tag)"
  echo "tool: vegeta $VEGETA_VERSION"
  echo "base: $BASE"
  echo "rate: $RATE"
  echo "duration_per_run: $DURATION"
  echo "repetitions: $REPS"
  echo "scenarios: $SCENARIOS"
  echo "client: $CLIENT_LABEL"
  echo "tickers: $(grep -vc '^#' tickers.txt)"
  echo "# Each run window below should be excluded from the production traffic metrics."
} >> "$ENVIRONMENT"

python3 ../lib/vegeta_csv.py --header --base "$BASE" --field scenario= --field run= > "$CSV"

first_run=1
for run in $(seq 1 "$REPS"); do
  for scenario in $SCENARIOS; do
    [ "$first_run" = 1 ] || sleep "$PAUSE_SECONDS"
    first_run=0
    python3 ../lib/api_targets.py "$scenario" --base "$BASE" --tickers tickers.txt \
      --slice "$((run - 1))" --slices "$REPS" > "$WORK/targets"
    wait_for_etl_free_window
    start=$(date -Iseconds)
    echo "-> $scenario run $run ($RATE for $DURATION) from $start"
    "$VEGETA" attack -targets="$WORK/targets" -rate="$RATE" -duration="$DURATION" \
        -timeout=30s -header "X-API-Key: $SYNDRA_BENCH_KEY" -name="$scenario" \
      | "$VEGETA" encode --to csv \
      | python3 ../lib/vegeta_csv.py --base "$BASE" --field "scenario=$scenario" --field "run=$run" \
      >> "$CSV"
    echo "window: $scenario run $run $start -> $(date -Iseconds)" >> "$ENVIRONMENT"
  done
done

echo "Data:        $CSV"
echo "Environment: $ENVIRONMENT"
