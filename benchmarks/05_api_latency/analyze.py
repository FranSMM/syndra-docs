#!/usr/bin/env python3
"""Experiment 05: latency percentiles per scenario, with bootstrap confidence intervals."""
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import stats  # noqa: E402

PERCENTILES = (50, 90, 95, 99)


def load_runs(csv_path):
    runs = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            runs[(row["scenario"], int(row["run"]))].append(row)
    return runs


def summarise(runs):
    by_scenario = defaultdict(lambda: {"first": [], "rest": [], "errors": 0, "codes": defaultdict(int)})
    for (scenario, _), rows in runs.items():
        rows.sort(key=lambda r: int(r["seq"]))
        agg = by_scenario[scenario]
        for i, row in enumerate(rows):
            agg["codes"][row["code"]] += 1
            if row["code"] != "200":
                agg["errors"] += 1
                continue
            # The first request of each run pays the TLS handshake and, in the
            # warm scenarios, the only cache miss: it is reported apart.
            (agg["first"] if i == 0 else agg["rest"]).append(float(row["latency_ms"]))
    return by_scenario


def main(csv_path):
    rng = random.Random(stats.SEED)
    header = ["scenario", "n", "errors", "codes", "first_median_ms"]
    for p in PERCENTILES:
        header += [f"p{p}_ms", f"p{p}_ci95_low", f"p{p}_ci95_high"]
    header.append("max_ms")
    print(",".join(header))

    for scenario, agg in summarise(load_runs(csv_path)).items():
        rest = sorted(agg["rest"])
        first = sorted(agg["first"])
        codes = " ".join(f"{c}:{k}" for c, k in sorted(agg["codes"].items()))
        row = [scenario, str(len(rest)), str(agg["errors"]), codes,
               f"{stats.percentile(first, 50):.1f}" if first else ""]
        if len(rest) >= 2:
            ci = stats.ci95_percentiles(rest, PERCENTILES, rng)
            for p in PERCENTILES:
                row += [f"{stats.percentile(rest, p):.1f}", f"{ci[p][0]:.1f}", f"{ci[p][1]:.1f}"]
            row.append(f"{rest[-1]:.1f}")
        print(",".join(row))


if __name__ == "__main__":
    main(sys.argv[1])
