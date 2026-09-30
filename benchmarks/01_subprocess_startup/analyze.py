#!/usr/bin/env python3
"""Experiment 01: statistical summary of the subprocess startup cost."""
import csv
import random
import statistics
import sys
from collections import defaultdict

SEED = 2026
RESAMPLES = 10_000


def median_ci95(values, rng):
    n = len(values)
    medians = sorted(
        statistics.median(rng.choices(values, k=n)) for _ in range(RESAMPLES)
    )
    return medians[int(0.025 * RESAMPLES)], medians[int(0.975 * RESAMPLES) - 1]


def main(csv_path):
    series = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            series[row["measurement"]].append((int(row["repetition"]), float(row["ms"])))

    rng = random.Random(SEED)
    print("measurement,n,first_ms,median_ms,p25_ms,p75_ms,ci95_low_ms,ci95_high_ms")
    for measurement, rows in series.items():
        rows.sort()
        first = rows[0][1]
        rest = [ms for _, ms in rows[1:]]
        if len(rest) < 2:
            print(f"{measurement},{len(rest)},{first:.0f},,,,,")
            continue
        p25, _, p75 = statistics.quantiles(rest, n=4)
        low, high = median_ci95(rest, rng)
        print(f"{measurement},{len(rest)},{first:.0f},{statistics.median(rest):.0f},"
              f"{p25:.0f},{p75:.0f},{low:.0f},{high:.0f}")


if __name__ == "__main__":
    main(sys.argv[1])
