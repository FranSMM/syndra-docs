#!/usr/bin/env python3
"""Experiment 06: latency percentiles per scenario, with bootstrap confidence intervals."""
import csv
import math
import random
import sys
from collections import defaultdict

SEED = 2026
RESAMPLES = 10_000
PERCENTILES = (50, 90, 95, 99)


def percentile(sorted_values, p):
    """Nearest-rank percentile: always an observed value, never an interpolation."""
    k = max(1, math.ceil(p / 100 * len(sorted_values)))
    return sorted_values[k - 1]


def ci95(values, ps, rng):
    n = len(values)
    samples = {p: [] for p in ps}
    for _ in range(RESAMPLES):
        s = sorted(rng.choices(values, k=n))
        for p in ps:
            samples[p].append(percentile(s, p))
    out = {}
    for p in ps:
        s = sorted(samples[p])
        out[p] = (s[int(0.025 * RESAMPLES)], s[int(0.975 * RESAMPLES) - 1])
    return out


def main(csv_path):
    runs = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            runs[(row["scenario"], int(row["run"]))].append(row)

    by_scenario = defaultdict(lambda: {"first": [], "rest": [], "errors": 0, "total": 0, "codes": defaultdict(int)})
    for (scenario, _), rows in runs.items():
        rows.sort(key=lambda r: int(r["seq"]))
        agg = by_scenario[scenario]
        for i, r in enumerate(rows):
            agg["total"] += 1
            agg["codes"][r["code"]] += 1
            if r["code"] != "200":
                agg["errors"] += 1
                continue
            # The first request of each run pays the TLS handshake and, in the
            # warm scenarios, the only cache miss: it is reported apart.
            (agg["first"] if i == 0 else agg["rest"]).append(float(r["latency_ms"]))

    rng = random.Random(SEED)
    header = ["scenario", "n", "errors", "codes", "first_median_ms"]
    for p in PERCENTILES:
        header += [f"p{p}_ms", f"p{p}_ci95_low", f"p{p}_ci95_high"]
    header.append("max_ms")
    print(",".join(header))
    for scenario, agg in by_scenario.items():
        rest = sorted(agg["rest"])
        codes = " ".join(f"{c}:{k}" for c, k in sorted(agg["codes"].items()))
        first = sorted(agg["first"])
        row = [scenario, str(len(rest)), str(agg["errors"]), codes,
               f"{percentile(first, 50):.1f}" if first else ""]
        if len(rest) >= 2:
            ci = ci95(rest, PERCENTILES, rng)
            for p in PERCENTILES:
                row += [f"{percentile(rest, p):.1f}", f"{ci[p][0]:.1f}", f"{ci[p][1]:.1f}"]
            row.append(f"{rest[-1]:.1f}")
        print(",".join(row))


if __name__ == "__main__":
    main(sys.argv[1])
