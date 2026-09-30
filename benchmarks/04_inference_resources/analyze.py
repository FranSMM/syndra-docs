#!/usr/bin/env python3
"""Experiment 04: FinBERT throughput and memory per mode and batch size."""
import csv
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import stats  # noqa: E402

HEADER = ["mode", "batch_size", "n", "first_ms", "median_ms", "ci95_low_ms", "ci95_high_ms",
          "articles_per_s", "cpu_cores_busy", "load_rss_mb", "peak_rss_mb", "speedup_vs_production"]


def main(csv_path):
    groups = defaultdict(list)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            groups[(row["mode"], int(row["batch_size"]))].append(row)

    rng = random.Random(stats.SEED)
    production = None
    summaries = []
    # Production first, so every batched row can be compared against it.
    for (mode, batch_size), rows in sorted(groups.items(), key=lambda kv: (kv[0][0] != "production", kv[0][1])):
        rows.sort(key=lambda r: int(r["rep"]))
        # The first repetition pays one-off allocations, so it is reported apart.
        rest = rows[1:]
        wall = [float(r["wall_ms"]) for r in rest]
        median = statistics.median(wall)
        low, high = stats.ci95(wall, statistics.median, rng)
        articles = int(rows[0]["articles"])
        cores = statistics.median(float(r["cpu_ms"]) / float(r["wall_ms"]) for r in rest)
        if mode == "production":
            production = median
        summaries.append([
            mode, batch_size, len(rest), rows[0]["wall_ms"], f"{median:.1f}", f"{low:.1f}", f"{high:.1f}",
            f"{articles / median * 1000:.1f}", f"{cores:.2f}", rows[0]["load_rss_mb"],
            f"{max(float(r['peak_rss_mb']) for r in rows):.1f}",
            f"{production / median:.2f}" if production else "",
        ])

    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(HEADER)
    writer.writerows(summaries)


if __name__ == "__main__":
    main(sys.argv[1])
