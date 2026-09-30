#!/usr/bin/env python3
"""Experiment 01: statistical summary of the subprocess startup cost."""
import csv
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import stats  # noqa: E402


def main(csv_path):
    series = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            series[row["measurement"]].append((int(row["repetition"]), float(row["ms"])))

    rng = random.Random(stats.SEED)
    print("measurement,n,first_ms,median_ms,p25_ms,p75_ms,ci95_low_ms,ci95_high_ms")
    for measurement, rows in series.items():
        rows.sort()
        # The first repetition pays the cold page cache, so it is reported apart.
        first = rows[0][1]
        rest = [ms for _, ms in rows[1:]]
        if len(rest) < 2:
            print(f"{measurement},{len(rest)},{first:.0f},,,,,")
            continue
        p25, _, p75 = statistics.quantiles(rest, n=4)
        low, high = stats.ci95(rest, statistics.median, rng)
        print(f"{measurement},{len(rest)},{first:.0f},{statistics.median(rest):.0f},"
              f"{p25:.0f},{p75:.0f},{low:.0f},{high:.0f}")


if __name__ == "__main__":
    main(sys.argv[1])
