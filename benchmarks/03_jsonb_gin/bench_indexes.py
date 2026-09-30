#!/usr/bin/env python3
"""Experiment 03 driver, run by measure.sh against the throwaway Postgres.

For each table size it builds a copy of `articles` with the first N rows, then
for each index variant it checks that the query returns the same rows as the
production one and times it with EXPLAIN ANALYZE. It talks to Postgres through
`docker exec psql`, so it needs nothing beyond the standard library.
"""
import argparse
import csv
import json
import re
import subprocess

TABLE = "bench_articles"

# The query the API runs (app/services/sentiment_service.py). LIMIT 40 is the
# default limit of 20 times the deduplication over-fetch factor of 2.
PRODUCTION_WHERE = "{ticker} = ANY(a.tickers)"
# `= ANY` cannot use a GIN index. Containment can, and for a single ticker it
# selects exactly the same rows.
CONTAINMENT_WHERE = "a.tickers @> ARRAY[{ticker}]::varchar[]"
QUERY = f"""
SELECT a.*, r.*
FROM {TABLE} a
LEFT OUTER JOIN raw_articles r ON r.id = a.raw_article_id
WHERE {{where}}
ORDER BY a.published_at DESC NULLS LAST
LIMIT 40"""

GIN_INDEX = ("bench_tickers_gin", f"CREATE INDEX bench_tickers_gin ON {TABLE} USING gin (tickers)")
# The existing published_at index is ascending with nulls last, which does not
# match the query's DESC NULLS LAST order, so it cannot feed the LIMIT directly.
ORDER_INDEX = ("bench_published_desc",
               f"CREATE INDEX bench_published_desc ON {TABLE} (published_at DESC NULLS LAST)")

VARIANTS = {
    "baseline": ([], PRODUCTION_WHERE),
    "gin": ([GIN_INDEX], CONTAINMENT_WHERE),
    "order_index": ([ORDER_INDEX], PRODUCTION_WHERE),
    "gin_and_order": ([GIN_INDEX, ORDER_INDEX], CONTAINMENT_WHERE),
}

QUERY_COLUMNS = ["size", "table_rows", "variant", "ticker_class", "ticker", "matches", "rep",
                 "execution_ms", "planning_ms", "shared_hit", "shared_read", "plan"]
INDEX_COLUMNS = ["size", "table_rows", "variant", "index", "build_ms", "size_bytes"]


class Postgres:
    def __init__(self, container):
        self.container = container

    def run(self, sql):
        result = subprocess.run(
            ["docker", "exec", "-i", self.container,
             "psql", "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "bench"],
            input=sql, text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def timed(self, sql):
        """Runs one statement and returns its server-side duration in ms."""
        out = self.run(f"\\timing on\n{sql};")
        return float(re.findall(r"Time: ([\d.]+) ms", out)[-1])


def sql_literal(value):
    return "'" + value.replace("'", "''") + "'"


def build_table(pg, size):
    limit = "" if size == "all" else f"LIMIT {int(size)}"
    # LIKE ... INCLUDING ALL copies the production indexes, so the baseline is
    # the schema production actually has.
    pg.run(f"""
        DROP TABLE IF EXISTS {TABLE};
        CREATE TABLE {TABLE} (LIKE articles INCLUDING ALL);
        INSERT INTO {TABLE} SELECT * FROM articles ORDER BY id {limit};""")
    pg.run(f"VACUUM ANALYZE {TABLE};")
    return int(pg.run(f"SELECT count(*) FROM {TABLE};"))


def pick_tickers(pg):
    """Three tickers by frequency: the most covered, a typical one that fills
    the LIMIT, and the rarest, where an ordered scan finds nothing to stop at."""
    rows = pg.run(f"""
        SELECT t, count(*) FROM {TABLE}, unnest(tickers) AS t
        GROUP BY t ORDER BY count(*) DESC, t;""").splitlines()
    counts = [(t, int(n)) for t, n in (r.split("|") for r in rows)]
    filling = [c for c in counts if c[1] >= 40]
    picks = {"common": counts[0], "rare": counts[-1]}
    if filling:
        picks["typical"] = filling[len(filling) // 2]
    return picks


def apply_variant(pg, indexes):
    pg.run(f"DROP INDEX IF EXISTS {GIN_INDEX[0]}; DROP INDEX IF EXISTS {ORDER_INDEX[0]};")
    built = []
    for name, ddl in indexes:
        build_ms = pg.timed(ddl)
        size = int(pg.run(f"SELECT pg_relation_size('{name}');"))
        built.append((name, build_ms, size))
    pg.run(f"ANALYZE {TABLE};")
    return built


def result_fingerprint(pg, where):
    # Ties on published_at may come back in any order, so the fingerprint is
    # the ordered list of timestamps, which is the same for any correct plan.
    return pg.run(f"""
        SELECT count(*) || ':' || md5(string_agg(coalesce(published_at::text, 'null'), ','
                                                 ORDER BY published_at DESC NULLS LAST))
        FROM ({QUERY.format(where=where)}) q;""")


def scans(plan):
    """The access paths of a plan, e.g. 'Seq Scan bench_articles; Index Scan raw_articles_pkey'."""
    found = []
    if "Scan" in plan["Node Type"]:
        found.append(f"{plan['Node Type']} {plan.get('Index Name') or plan.get('Relation Name', '')}".strip())
    for child in plan.get("Plans", []):
        found.extend(scans(child))
    return found


def explain(pg, where):
    out = json.loads(pg.run(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {QUERY.format(where=where)};"))[0]
    top = out["Plan"]
    return {
        "execution_ms": f"{out['Execution Time']:.3f}",
        "planning_ms": f"{out['Planning Time']:.3f}",
        "shared_hit": top.get("Shared Hit Blocks", 0),
        "shared_read": top.get("Shared Read Blocks", 0),
        "plan": "; ".join(scans(top)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    parser.add_argument("--sizes", required=True, help="space separated row counts, or 'all'")
    parser.add_argument("--reps", type=int, required=True)
    parser.add_argument("--queries-csv", required=True)
    parser.add_argument("--indexes-csv", required=True)
    parser.add_argument("--environment", required=True)
    args = parser.parse_args()

    pg = Postgres(args.container)
    with open(args.environment, "a", encoding="utf-8") as env:
        env.write(pg.run("SELECT 'server_version: ' || version();") + "\n")
        for setting in ("shared_buffers", "work_mem", "effective_cache_size",
                        "random_page_cost", "max_parallel_workers_per_gather"):
            env.write(f"{setting}: {pg.run(f'SHOW {setting};')}\n")

    with open(args.queries_csv, "w", newline="", encoding="utf-8") as qf, \
         open(args.indexes_csv, "w", newline="", encoding="utf-8") as xf:
        queries = csv.DictWriter(qf, fieldnames=QUERY_COLUMNS, lineterminator="\n")
        indexes = csv.DictWriter(xf, fieldnames=INDEX_COLUMNS, lineterminator="\n")
        queries.writeheader()
        indexes.writeheader()

        for size in args.sizes.split():
            table_rows = build_table(pg, size)
            tickers = pick_tickers(pg)
            with open(args.environment, "a", encoding="utf-8") as env:
                picked = ", ".join(f"{cls}={t} ({n})" for cls, (t, n) in tickers.items())
                env.write(f"tickers at size {size} ({table_rows} rows): {picked}\n")
            print(f"-> size {size}: {table_rows} rows, tickers {tickers}", flush=True)

            expected = {}
            for variant, (variant_indexes, where_template) in VARIANTS.items():
                for name, build_ms, size_bytes in apply_variant(pg, variant_indexes):
                    indexes.writerow({"size": size, "table_rows": table_rows, "variant": variant,
                                      "index": name, "build_ms": f"{build_ms:.1f}", "size_bytes": size_bytes})
                for ticker_class, (ticker, matches) in tickers.items():
                    where = where_template.format(ticker=sql_literal(ticker))
                    fingerprint = result_fingerprint(pg, where)
                    # Every variant must return what production returns, or its
                    # timing measures a different query.
                    if expected.setdefault(ticker_class, fingerprint) != fingerprint:
                        raise SystemExit(f"{variant} returns different rows for {ticker} at size {size}")
                    for rep in range(1, args.reps + 1):
                        queries.writerow({"size": size, "table_rows": table_rows, "variant": variant,
                                          "ticker_class": ticker_class, "ticker": ticker,
                                          "matches": matches, "rep": rep, **explain(pg, where)})
                qf.flush()
                print(f"   {variant} done", flush=True)


if __name__ == "__main__":
    main()
