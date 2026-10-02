# Helpers shared by the measure.sh scripts. Source it; it does nothing on its own.
#
# Configuration comes from the repository .env, which is not in git, so no
# address or credential is ever written into a benchmark file.

BENCH_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$BENCH_LIB_DIR" rev-parse --show-toplevel 2>/dev/null || (cd "$BENCH_LIB_DIR/../.." && pwd))"
BENCH_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/syndra-bench"

# read_env KEY: value of KEY in the repository .env, empty if absent. Always
# succeeds: a missing key must reach the caller's own message, not end a
# `set -e` script in silence.
read_env() {
  grep -E "^$1=" "$REPO_ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d "\"' \r" || true
}

# Export HOST=user@machine to measure somewhere other than the VPS in .env.
vps_host() {
  if [ -n "${HOST:-}" ]; then
    echo "$HOST"
    return
  fi
  local user ip
  user=$(read_env VPS_USER)
  ip=$(read_env VPS_IP)
  if [ -z "$user" ] || [ -z "$ip" ]; then
    echo "VPS_USER or VPS_IP missing from $REPO_ROOT/.env" >&2
    return 1
  fi
  echo "$user@$ip"
}

# vps CMD: runs CMD on the VPS, forwarding stdin.
vps() {
  ssh -o BatchMode=yes -o ConnectTimeout=10 "$(vps_host)" "$@"
}

# vps_psql app|prefect [psql flags]: runs the SQL on stdin against production.
# The session is forced read-only, so a mistake in a benchmark cannot write.
vps_psql() {
  local db='$POSTGRES_DB'
  [ "$1" = prefect ] && db=prefect_db
  shift
  vps "docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' syndra_postgres \
       sh -c 'exec psql -X -q -v ON_ERROR_STOP=1 -U \"\$POSTGRES_USER\" -d \"$db\" $*'"
}

# Tag of the ETL image production is running, or "unknown" without SSH access.
deployed_etl_tag() {
  local dir
  dir=$(read_env DEPLOY_DIR)
  vps "grep -E '^ETL_TAG=' '${dir:-syndra-deploy}/.env' | cut -d= -f2" 2>/dev/null || echo unknown
}

new_stamp() {
  date +%Y%m%d_%H%M%S
}

# write_environment_header FILE: the fields every experiment records.
write_environment_header() {
  {
    echo "date: $(date -Iseconds)"
    echo "repo_commit: $(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    # Results and documents are not measured code; any other change or new file is.
    if [ -n "$(git -C "$REPO_ROOT" status --porcelain --untracked-files=all -- . ':(exclude,glob)benchmarks/*/results/**' ':(exclude)docs' 2>/dev/null)" ]; then
      echo "dirty_tree: yes"
    else
      echo "dirty_tree: no"
    fi
  } > "$1"
}

# ensure_vegeta: prints the path of a verified vegeta binary, downloading it once.
VEGETA_VERSION=12.13.0
VEGETA_SHA256=e8759ce45c14e18374bdccd3ba6068197bc3a9f9b7e484db3837f701b9d12e61
ensure_vegeta() {
  local dir="$BENCH_CACHE/vegeta-$VEGETA_VERSION"
  local tarball="vegeta_${VEGETA_VERSION}_linux_amd64.tar.gz"
  if [ ! -x "$dir/vegeta" ]; then
    mkdir -p "$dir"
    curl -fsSL -o "$dir/$tarball" \
      "https://github.com/tsenart/vegeta/releases/download/v$VEGETA_VERSION/$tarball"
    # Pinned here rather than read from the release: a checksum fetched from the
    # same place as the binary proves nothing if that place is compromised.
    echo "$VEGETA_SHA256  $dir/$tarball" | sha256sum -c --quiet >&2
    tar -xzf "$dir/$tarball" -C "$dir" vegeta
    rm "$dir/$tarball"
  fi
  echo "$dir/vegeta"
}
