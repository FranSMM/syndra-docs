#!/usr/bin/env bash
# Experiment 06: production resource use and server-side latency, from the
# metrics Prometheus, cAdvisor and node_exporter already collect.
# Read-only: GET requests to Prometheus on the VPS; nothing is written there.
set -euo pipefail
cd "$(dirname "$0")"
source ../lib/common.sh

# The 05 run whose request windows are looked up in the server histogram, and
# the 04 run the production scheduler peak is compared with.
LATENCY_ENV="${LATENCY_ENV:-$(ls -t ../05_api_latency/results/latency_*_environment.txt 2>/dev/null | head -1)}"
INFERENCE_SUMMARY="${INFERENCE_SUMMARY:-$(ls -t ../04_inference_resources/results/inference_*_summary.csv 2>/dev/null | head -1)}"
SCHEDULER_DAYS="${SCHEDULER_DAYS:-7}"

# export.py travels through stdin, so no file is ever copied to the VPS.
export_dataset() {
  vps "python3 - $*" < export.py
}

mkdir -p results
STAMP="$(new_stamp)"
PREFIX="results/production_${STAMP}"
ENVIRONMENT="${PREFIX}_environment.txt"

PERIOD="$(export_dataset period)"
# The VPS clock sets the period: the WSL clock can drift after a suspend.
NOW=$(sed -n 's/^now_epoch: //p' <<< "$PERIOD")
DATA_START=$(sed -n 's/^data_start_epoch: //p' <<< "$PERIOD")
START=$(( (DATA_START + 899) / 900 * 900 ))
END=$(( NOW / 900 * 900 ))
SCHEDULER_START=$(( END - SCHEDULER_DAYS * 86400 ))

WINDOWS=()
if [ -n "$LATENCY_ENV" ]; then
  while read -r _ scenario _ run start _ end; do
    WINDOWS+=("$scenario,$run,$(date -d "$start" +%s),$(date -d "$end" +%s)")
  done < <(grep '^window:' "$LATENCY_ENV")
fi

write_environment_header "$ENVIRONMENT"
{
  grep -v '^now_epoch\|^data_start_epoch' <<< "$PERIOD"
  echo "period: $(date -u -d "@$START" +%FT%TZ) to $(date -u -d "@$END" +%FT%TZ)"
  echo "scheduler_detail_days: $SCHEDULER_DAYS"
  echo "latency_windows_from: ${LATENCY_ENV:-none}"
  echo "latency_client_summary: ${LATENCY_ENV:+${LATENCY_ENV%_environment.txt}_summary.csv}"
  echo "inference_summary: ${INFERENCE_SUMMARY:-none}"
  # The ETL interval is anchored at the last deploy, so its minute moves.
  vps_psql prefect -At <<'SQL'
SELECT 'etl_schedule: ' || d.name || ' ' || s.schedule::text
FROM deployment d JOIN deployment_schedule s ON s.deployment_id = d.id;
SQL
  # Docker's own count of restarts by the restart policy, for the containers
  # running now. A deploy recreates a container and resets it to 0.
  echo "# Current containers: restarts since creation, start, and whether the last exit was an OOM kill."
  vps "docker inspect -f '{{.Name}} restarts={{.RestartCount}} started={{.State.StartedAt}} oom_killed={{.State.OOMKilled}}' \$(docker ps -q)" \
    | sed 's|^/|container_state: |'
  # What the disk holds, to explain its growth: data or Docker images.
  vps "docker system df --format '{{.Type}}: {{.Size}} ({{.Reclaimable}} reclaimable)'" | sed 's|^|docker_disk: |'
} >> "$ENVIRONMENT"

echo "-> containers";  export_dataset containers "$START" "$END" > "${PREFIX}_containers.csv"
echo "-> host";        export_dataset host "$START" "$END" > "${PREFIX}_host.csv"
echo "-> storage";     export_dataset storage "$START" "$END" > "${PREFIX}_storage.csv"
echo "-> cpu";         export_dataset cpu "$START" "$END" > "${PREFIX}_cpu.csv"
echo "-> scheduler";   export_dataset scheduler "$SCHEDULER_START" "$END" > "${PREFIX}_scheduler.csv"
echo "-> series";      export_dataset series > "${PREFIX}_series.csv"
# When each ETL run really happened, to tell its CPU and memory from the rest.
echo "-> etl runs"
vps_psql prefect > "${PREFIX}_etl_runs.csv" <<SQL
COPY (
  SELECT extract(epoch FROM start_time)::bigint AS start_epoch,
         extract(epoch FROM end_time)::bigint AS end_epoch,
         state_type AS state
  FROM flow_run
  WHERE start_time >= to_timestamp($START) AND end_time IS NOT NULL
  ORDER BY start_time
) TO STDOUT WITH (FORMAT csv, HEADER true);
SQL
if [ "${#WINDOWS[@]}" -gt 0 ]; then
  echo "-> latency (${#WINDOWS[@]} windows)"
  export_dataset latency "${WINDOWS[@]}" > "${PREFIX}_latency.csv"
fi

echo "Data:        ${PREFIX}_*.csv"
echo "Environment: $ENVIRONMENT"
