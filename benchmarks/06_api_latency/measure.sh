#!/usr/bin/env bash
# Experiment 06: API latency at the load of a single client.
# Runs against production at 0.4 requests/s, well under the 100/min per-key limit.
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ../..)"

: "${SYNDRA_BENCH_KEY:?export SYNDRA_BENCH_KEY with a dedicated test key, never the demo one}"
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

VEGETA_VERSION=12.13.0
VEGETA_SHA256=e8759ce45c14e18374bdccd3ba6068197bc3a9f9b7e484db3837f701b9d12e61
TOOLS="${XDG_CACHE_HOME:-$HOME/.cache}/syndra-bench/vegeta-$VEGETA_VERSION"
VEGETA="$TOOLS/vegeta"
if [ ! -x "$VEGETA" ]; then
  mkdir -p "$TOOLS"
  tarball="vegeta_${VEGETA_VERSION}_linux_amd64.tar.gz"
  curl -fsSL -o "$TOOLS/$tarball" \
    "https://github.com/tsenart/vegeta/releases/download/v$VEGETA_VERSION/$tarball"
  echo "$VEGETA_SHA256  $TOOLS/$tarball" | sha256sum -c --quiet
  tar -xzf "$TOOLS/$tarball" -C "$TOOLS" vegeta
  rm "$TOOLS/$tarball"
fi

minutes() { case "$1" in *m) echo "${1%m}";; *s) echo $(( (${1%s} + 59) / 60 ));; *) echo 60;; esac; }
DUR_MIN=$(minutes "$DURATION")

# The ETL runs at :58 every hour and competes for the same two cores. A run must
# fit between :05 and :55, or its latencies measure the pipeline, not the API.
wait_for_window() {
  [ "$ETL_GUARD" = 1 ] || return 0
  [ "$DUR_MIN" -le 50 ] || { echo "DURATION must be 50m or less to fit between ETL runs" >&2; exit 1; }
  while :; do
    m=$((10#$(date +%M)))
    if [ "$m" -ge 5 ] && [ $((m + DUR_MIN)) -le 55 ]; then return 0; fi
    sleep 20
  done
}

mkdir -p results
STAMP="$(date +%Y%m%d_%H%M%S)"
CSV="results/latency_${STAMP}.csv"
ENVIRONMENT="results/latency_${STAMP}_environment.txt"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

read_env() { grep -E "^$1=" "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"' \r"; }
deployed_etl="unknown"
if [ -n "$(read_env VPS_IP)" ]; then
  deployed_etl=$(ssh -o BatchMode=yes -o ConnectTimeout=10 "$(read_env VPS_USER)@$(read_env VPS_IP)" \
    "grep -E '^ETL_TAG=' ~/syndra-deploy/.env | cut -d= -f2" 2>/dev/null || echo unknown)
fi

{
  echo "date: $(date -Iseconds)"
  echo "repo_commit: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  # With uncommitted changes the commit above does not identify the measured code.
  echo "dirty_tree: $(test -n "$(git status --porcelain 2>/dev/null)" && echo yes || echo no)"
  echo "deployed_etl_tag: $deployed_etl"
  echo "tool: vegeta $VEGETA_VERSION"
  echo "base: $BASE"
  echo "rate: $RATE"
  echo "duration_per_run: $DURATION"
  echo "repetitions: $REPS"
  echo "scenarios: $SCENARIOS"
  echo "client: $CLIENT_LABEL"
  echo "tickers: $(grep -vc '^#' tickers.txt)"
  echo "# Each run window below should be excluded from the production traffic metrics."
} > "$ENVIRONMENT"

grep -v '^#' tickers.txt > "$WORK/tickers"

# One targets file per scenario and run. Cold search queries are unique across
# the whole session, drawn with a fixed seed so the session can be repeated.
make_targets() {  # $1 scenario, $2 run
  python3 - "$1" "$2" "$BASE" "$WORK/tickers" > "$WORK/targets" <<'PY'
import random, sys, urllib.parse
scenario, run, base, tickers_file = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
tickers = [t.strip() for t in open(tickers_file) if t.strip()]
topics = ["earnings guidance", "analyst downgrade", "supply chain risk", "regulatory probe",
          "dividend increase", "share buyback", "layoffs", "merger talks", "product launch",
          "lawsuit", "revenue miss", "record quarter"]
if scenario == "sentiment_warm":
    urls = [f"{base}/api/v1/sentiment/NVDA"]
elif scenario == "sentiment_cold":
    urls = [f"{base}/api/v1/sentiment/{urllib.parse.quote(t)}" for t in tickers]
elif scenario == "search_warm":
    urls = [f"{base}/api/v1/search/semantic?query=" + urllib.parse.quote("semiconductor export restrictions")]
elif scenario == "search_cold":
    pool = [f"{t} {topic}" for t in tickers for topic in topics]
    random.Random(2026).shuffle(pool)
    size = len(pool) // 3
    urls = [f"{base}/api/v1/search/semantic?query=" + urllib.parse.quote(q)
            for q in pool[(run - 1) % 3 * size:((run - 1) % 3 + 1) * size]]
else:
    sys.exit(f"unknown scenario {scenario}")
for u in urls:
    print(f"GET {u}")
PY
}

echo "scenario,run,seq,timestamp,code,latency_ms,bytes_in,error,url" > "$CSV"
first=1
for run in $(seq 1 "$REPS"); do
  for scenario in $SCENARIOS; do
    [ "$first" = 1 ] || sleep "$PAUSE_SECONDS"
    first=0
    make_targets "$scenario" "$run"
    wait_for_window
    start=$(date -Iseconds)
    echo "-> $scenario run $run ($RATE for $DURATION) from $start"
    "$VEGETA" attack -targets="$WORK/targets" -rate="$RATE" -duration="$DURATION" \
        -timeout=30s -header "X-API-Key: $SYNDRA_BENCH_KEY" -name="$scenario" \
      | "$VEGETA" encode --to csv > "$WORK/raw.csv"
    echo "window: $scenario run $run $start -> $(date -Iseconds)" >> "$ENVIRONMENT"
    # vegeta CSV: timestamp,code,latency_ns,bytes_out,bytes_in,error,body_b64,attack,seq,method,url,headers_b64.
    # Response bodies and headers are dropped: they are not needed and inflate the file.
    python3 - "$scenario" "$run" "$WORK/raw.csv" "$BASE" >> "$CSV" <<'PY'
import csv, sys
scenario, run, path, base = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
w = csv.writer(sys.stdout, lineterminator="\n")
for r in csv.reader(open(path, newline="")):
    ts, code, lat_ns, _, bytes_in, err, _, _, seq, _, url = r[:11]
    w.writerow([scenario, run, seq, ts, code, f"{int(lat_ns) / 1e6:.3f}", bytes_in, err, url.replace(base, "")])
PY
  done
done

echo "Data:        $CSV"
echo "Environment: $ENVIRONMENT"
