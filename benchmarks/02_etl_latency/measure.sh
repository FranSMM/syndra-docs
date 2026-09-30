#!/usr/bin/env bash
# Experiment 02: ETL latency per stage, from the history Prefect already records.
# Read-only: exports durations from prefect_db and generates no load.
set -euo pipefail
cd "$(dirname "$0")"
source ../lib/common.sh

mkdir -p results
STAMP="$(new_stamp)"
CSV="results/etl_${STAMP}.csv"
ENVIRONMENT="results/etl_${STAMP}_environment.txt"

write_environment_header "$ENVIRONMENT"
{
  echo "deployed_etl_tag: $(deployed_etl_tag)"
  echo "prefect_server_image: $(vps "docker inspect -f '{{.Config.Image}}' syndra_prefect_server")"
  vps_psql prefect -At <<'SQL'
SELECT 'prefect_db_revision: ' || version_num FROM alembic_version;
SELECT 'flow_runs: ' || count(*) || ' (' || min(start_time)::date || ' to ' || max(start_time)::date || ')' FROM flow_run;
SELECT 'task_runs: ' || count(*) FROM task_run;
SQL
} >> "$ENVIRONMENT"

# One row per task run plus one per flow run (stage "flow_total"), with the
# number of feeds that run processed. The stage name loses Prefect's hash
# suffix, the same normalisation the ETL metrics use (ADR 041).
vps_psql prefect > "$CSV" <<'SQL'
COPY (
  WITH feeds AS (
    SELECT flow_run_id, max(substring(message FROM 'BYOS: (\d+) active')::int) AS n_feeds
    FROM log
    WHERE message LIKE 'BYOS:%'
    GROUP BY flow_run_id
  ),
  runs AS (
    SELECT tr.flow_run_id,
           regexp_replace(tr.name, '-[0-9a-f]+$', '') AS stage,
           tr.state_type,
           tr.total_run_time
    FROM task_run tr
    UNION ALL
    SELECT fr.id, 'flow_total', fr.state_type, fr.total_run_time
    FROM flow_run fr
  )
  SELECT r.flow_run_id,
         to_char(fr.start_time AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS flow_start,
         f.n_feeds,
         r.stage,
         r.state_type AS state,
         round(extract(epoch FROM r.total_run_time)::numeric, 3) AS seconds
  FROM runs r
  JOIN flow_run fr ON fr.id = r.flow_run_id
  LEFT JOIN feeds f ON f.flow_run_id = r.flow_run_id
  WHERE fr.start_time IS NOT NULL
  ORDER BY fr.start_time, r.stage
) TO STDOUT WITH (FORMAT csv, HEADER true);
SQL

echo "Data:        $CSV ($(($(wc -l < "$CSV") - 1)) rows)"
echo "Environment: $ENVIRONMENT"
