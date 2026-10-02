#!/usr/bin/env bash
# Experiment 07: why the ML stages barely grow with the number of articles.
# Read-only: stage durations and batch sizes from prefect_db, and timed imports
# and model loads inside the production scheduler, kept away from the ETL.
set -euo pipefail
cd "$(dirname "$0")"
source ../lib/common.sh

CONTAINER="${CONTAINER:-syndra_scheduler}"
REPS="${REPS:-30}"
# A block of REPS repetitions only starts with this much time left before the
# next ETL run, so the two never share the cores.
BLOCK_BUDGET_S="${BLOCK_BUDGET_S:-600}"
MEASUREMENTS="python_empty import_torch_transformers import_sentiment_stage load_sentiment_models
  load_sentiment_models_offline import_vector_stage load_vector_model load_vector_model_offline"

# The ETL interval is anchored at the last deploy, so the next run is read
# from Prefect instead of being assumed at a fixed minute.
wait_for_etl_gap() {
  local now next active
  while :; do
    IFS='|' read -r now next active < <(vps_psql prefect -At <<'SQL'
SELECT extract(epoch FROM now())::bigint,
       coalesce(extract(epoch FROM min(expected_start_time)
         FILTER (WHERE state_type = 'SCHEDULED' AND expected_start_time > now() - interval '5 minutes'))::bigint, 0),
       count(*) FILTER (WHERE state_type IN ('RUNNING', 'PENDING'))
FROM flow_run;
SQL
)
    if [ "$active" = 0 ] && { [ "$next" = 0 ] || [ $((next - now)) -ge "$BLOCK_BUDGET_S" ]; }; then
      return 0
    fi
    sleep 30
  done
}

mkdir -p results
STAMP="$(new_stamp)"
PREFIX="results/ml_${STAMP}"
ENVIRONMENT="${PREFIX}_environment.txt"

write_environment_header "$ENVIRONMENT"
{
  echo "repetitions: $REPS"
  vps "
    echo image: \$(docker inspect -f '{{.Config.Image}}' $CONTAINER)
    echo cores: \$(nproc)
    echo scheduler_started: \$(docker inspect -f '{{.State.StartedAt}}' $CONTAINER)
    echo hf_hub_offline_in_container: \$(docker exec $CONTAINER sh -c 'echo \${HF_HUB_OFFLINE:-unset}')
    docker exec $CONTAINER python -c 'import sys, torch, transformers, sentence_transformers; print(\"python:\", sys.version.split()[0]); print(\"torch:\", torch.__version__); print(\"transformers:\", transformers.__version__); print(\"sentence_transformers:\", sentence_transformers.__version__)'
  "
  echo "prefect_db_revision: $(vps_psql prefect -At <<< 'SELECT version_num FROM alembic_version;')"
} >> "$ENVIRONMENT"

# One row per ML stage run. N is the sum of the batch sizes the stage logged;
# a run that logged its "nothing to do" line has N = 0, and a run that logged
# neither (code older than those lines) has N empty: unknown, not zero.
echo "-> stage runs from prefect_db"
vps_psql prefect > "${PREFIX}_runs.csv" <<'SQL'
COPY (
  WITH stage_runs AS (
    SELECT id, regexp_replace(name, '-[0-9a-f]+$', '') AS stage,
           start_time, state_type, total_run_time
    FROM task_run
    WHERE name LIKE 'MLOps:%' AND start_time IS NOT NULL
  ),
  batches AS (
    SELECT l.task_run_id, sum(m[1]::int) AS n_articles, count(*) AS n_batches
    FROM log l, regexp_matches(l.message, '(?:Processing|Encoding) batch of (\d+) articles', 'g') AS m
    WHERE l.task_run_id IN (SELECT id FROM stage_runs)
    GROUP BY l.task_run_id
  ),
  empty_runs AS (
    SELECT DISTINCT task_run_id FROM log
    WHERE task_run_id IN (SELECT id FROM stage_runs)
      AND message ~ 'No more pending articles|Found 0 Silver articles'
  )
  SELECT to_char(s.start_time AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS stage_start,
         s.stage,
         s.state_type AS state,
         round(extract(epoch FROM s.total_run_time)::numeric, 3) AS seconds,
         CASE WHEN b.task_run_id IS NOT NULL THEN b.n_articles::text
              WHEN e.task_run_id IS NOT NULL THEN '0'
              ELSE '' END AS n_articles,
         coalesce(b.n_batches, 0) AS n_batches
  FROM stage_runs s
  LEFT JOIN batches b ON b.task_run_id = s.id
  LEFT JOIN empty_runs e ON e.task_run_id = s.id
  ORDER BY s.start_time, s.stage
) TO STDOUT WITH (FORMAT csv, HEADER true);
SQL

echo "measurement,repetition,ms" > "${PREFIX}_probe.csv"
for name in $MEASUREMENTS; do
  wait_for_etl_gap
  echo "-> $name ($REPS repetitions, from $(date +%H:%M:%S))"
  vps "docker exec -i $CONTAINER python - $name $REPS" < probe.py >> "${PREFIX}_probe.csv"
done

echo "Runs:        ${PREFIX}_runs.csv ($(($(wc -l < "${PREFIX}_runs.csv") - 1)) rows)"
echo "Probe:       ${PREFIX}_probe.csv"
echo "Environment: $ENVIRONMENT"
