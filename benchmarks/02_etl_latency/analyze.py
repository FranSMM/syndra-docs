#!/usr/bin/env python3
"""Experiment 02: ETL stage durations by week and by number of feeds.

Two views, one CSV:
  weekly     median and p95 per stage and ISO week, to see how latency evolved
  feeds      median per stage for each feed count, and the difference between
             the largest and smallest count, to separate a step caused by adding
             sources from day-to-day noise
"""
import csv
import random
import statistics
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import stats  # noqa: E402

HEADER = ["view", "group", "stage", "n", "median_s", "ci95_low_s", "ci95_high_s", "p95_s"]

# The extract task was renamed in April 2026. Same stage, so it is merged here;
# the raw CSV keeps the name Prefect recorded.
STAGE_ALIASES = {"Extract Scrapy Spider": "Extract: Generic RSS Spiders"}


def load_completed(csv_path):
    """Completed runs as (stage, iso_week, n_feeds, seconds)."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["state"] != "COMPLETED" or not row["seconds"]:
                continue
            year, week, _ = date.fromisoformat(row["flow_start"][:10]).isocalendar()
            feeds = int(row["n_feeds"]) if row["n_feeds"] else None
            stage = STAGE_ALIASES.get(row["stage"], row["stage"])
            rows.append((stage, f"{year}-W{week:02d}", feeds, float(row["seconds"])))
    return rows


def summary_row(view, group, stage, values, rng):
    ordered = sorted(values)
    low, high = stats.ci95(values, statistics.median, rng)
    return [view, group, stage, len(values), f"{statistics.median(values):.3f}",
            f"{low:.3f}", f"{high:.3f}", f"{stats.percentile(ordered, 95):.3f}"]


def weekly_view(rows, rng):
    groups = defaultdict(list)
    for stage, week, _, seconds in rows:
        groups[(week, stage)].append(seconds)
    for (week, stage), values in sorted(groups.items()):
        yield summary_row("weekly", week, stage, values, rng)


def feeds_view(rows, rng):
    groups = defaultdict(list)
    for stage, _, feeds, seconds in rows:
        # Runs from before the feed count was logged cannot be attributed.
        if feeds is not None:
            groups[(stage, feeds)].append(seconds)
    for (stage, feeds), values in sorted(groups.items()):
        yield summary_row("feeds", f"{feeds} feeds", stage, values, rng)

    by_stage = defaultdict(dict)
    for (stage, feeds), values in groups.items():
        by_stage[stage][feeds] = values
    for stage, per_count in sorted(by_stage.items()):
        if len(per_count) < 2:
            continue
        fewest, most = min(per_count), max(per_count)
        a, b = per_count[fewest], per_count[most]
        low, high = stats.ci95_difference(a, b, statistics.median, rng)
        diff = statistics.median(b) - statistics.median(a)
        # The difference row reports the change in median, not a p95.
        yield ["feeds_difference", f"{most} vs {fewest} feeds", stage, len(a) + len(b),
               f"{diff:.3f}", f"{low:.3f}", f"{high:.3f}", ""]


def main(csv_path):
    rows = load_completed(csv_path)
    rng = random.Random(stats.SEED)
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(HEADER)
    for out in weekly_view(rows, rng):
        writer.writerow(out)
    for out in feeds_view(rows, rng):
        writer.writerow(out)


if __name__ == "__main__":
    main(sys.argv[1])
