#!/usr/bin/env python3
"""Experiment 03: query time per table size, index variant and ticker class."""
import csv
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import stats  # noqa: E402

HEADER = ["table_rows", "variant", "ticker_class", "ticker", "matches", "n", "first_ms",
          "median_ms", "ci95_low_ms", "ci95_high_ms", "p95_ms", "speedup_vs_baseline", "plan"]


def load_groups(csv_path):
    groups = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (int(row["table_rows"]), row["variant"], row["ticker_class"])
            groups[key].append(row)
    return groups


def main(csv_path):
    groups = load_groups(csv_path)
    rng = random.Random(stats.SEED)
    medians = {}
    rows_out = []
    for key, rows in sorted(groups.items()):
        rows.sort(key=lambda r: int(r["rep"]))
        # The first execution after building the index reads from disk; the
        # rest measure the warm cache. The first is reported apart.
        first = float(rows[0]["execution_ms"])
        rest = [float(r["execution_ms"]) for r in rows[1:]]
        median = statistics.median(rest)
        medians[key] = median
        low, high = stats.ci95(rest, statistics.median, rng)
        plan = Counter(r["plan"] for r in rows[1:]).most_common(1)[0][0]
        rows_out.append((key, rows[0], len(rest), first, median, low, high,
                         stats.percentile(sorted(rest), 95), plan))

    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(HEADER)
    for (table_rows, variant, ticker_class), sample, n, first, median, low, high, p95, plan in rows_out:
        baseline = medians.get((table_rows, "baseline", ticker_class))
        speedup = f"{baseline / median:.2f}" if baseline and median else ""
        writer.writerow([table_rows, variant, ticker_class, sample["ticker"], sample["matches"], n,
                         f"{first:.3f}", f"{median:.3f}", f"{low:.3f}", f"{high:.3f}", f"{p95:.3f}",
                         speedup, plan])


if __name__ == "__main__":
    main(sys.argv[1])
