#!/usr/bin/env python3
"""Experiment 07: fixed and per-article cost of the ML stages, and what the
fixed cost is made of.

Usage: python3 analyze.py results/ml_YYYYMMDD_HHMMSS

Prints one CSV, view,subject,metric,value,ci95_low,ci95_high,unit.
"""
import csv
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import stats  # noqa: E402

# Per stage: the probe measurements of its import, and of its model load with
# and without the Hugging Face hub reachable.
STAGES = {
    "MLOps: Sentiment Enrichment": ("import_sentiment_stage", "load_sentiment_models", "load_sentiment_models_offline"),
    "MLOps: Vector Indexing": ("import_vector_stage", "load_vector_model", "load_vector_model_offline"),
}
N_BINS = ((1, 5), (6, 10), (11, 20), (21, 50), (51, 100), (101, 10_000))

out = csv.writer(sys.stdout)


def emit(view, subject, metric, value, ci=None, unit=""):
    low, high = ci if ci else ("", "")
    out.writerow([view, subject, metric, value, low, high, unit])


def s(seconds):
    return f"{seconds:.2f}"


def fit(points):
    """Least-squares intercept and slope of seconds = a + b * N."""
    n = len(points)
    mean_n = sum(p[0] for p in points) / n
    mean_s = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mean_n) ** 2 for p in points)
    sxy = sum((p[0] - mean_n) * (p[1] - mean_s) for p in points)
    slope = sxy / sxx
    return mean_s - slope * mean_n, slope


def read_environment(path):
    environment = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if ": " in line and not line.startswith("#"):
            key, value = line.split(": ", 1)
            environment[key] = value
    return environment


def stage_runs(path, since=None):
    """{stage: [(N, seconds)]} for completed runs whose N is known."""
    runs = defaultdict(list)
    unknown = defaultdict(int)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["state"] != "COMPLETED" or (since and row["stage_start"] < since):
                continue
            if row["n_articles"] == "":
                unknown[row["stage"]] += 1
                continue
            runs[row["stage"]].append((int(row["n_articles"]), float(row["seconds"])))
    return runs, unknown


def scaling(view, runs, unknown, rng):
    """The fit per stage, returned so the breakdown can use it."""
    fits = {}
    for stage, points in runs.items():
        empty = sorted(p[1] for p in points if p[0] == 0)
        loaded = [p for p in points if p[0] > 0]
        emit(view, stage, "runs_n_unknown", unknown[stage], unit="excluded: no batch line in the log")
        emit(view, stage, "runs_n_zero", len(empty))
        if empty:
            emit(view, stage, "median_seconds_n_zero", s(statistics.median(empty)),
                 tuple(s(x) for x in stats.ci95(empty, statistics.median, rng)), "s, no model loaded")
        emit(view, stage, "runs_n_positive", len(loaded))
        emit(view, stage, "median_n", statistics.median(p[0] for p in loaded), unit="articles")
        emit(view, stage, "median_seconds_n_positive", s(statistics.median(p[1] for p in loaded)), unit="s")

        # With N = 0 the model is never loaded, so those runs follow another
        # law; the fit only covers runs that loaded it.
        a, b = fit(loaded)
        ci_a, ci_b = stats.ci95_each(loaded, fit, rng)
        emit(view, stage, "fixed_a", s(a), (s(ci_a[0]), s(ci_a[1])), "s per run")
        emit(view, stage, "per_article_b", f"{1000 * b:.1f}", (f"{1000 * ci_b[0]:.1f}", f"{1000 * ci_b[1]:.1f}"), "ms per article")
        fits[stage] = (a, b, statistics.median(p[0] for p in loaded))

        # Medians by range of N show whether a straight line is a fair summary.
        for low, high in N_BINS:
            group = [p[1] for p in loaded if low <= p[0] <= high]
            if group:
                emit(view, stage, f"median_seconds_n_{low}_{high}", s(statistics.median(group)), unit=f"s, {len(group)} runs")
    return fits


def probe(path, rng):
    by_name = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_name[row["measurement"]].append((int(row["repetition"]), float(row["ms"]) / 1000))
    rest = {}
    for name, reps in by_name.items():
        reps.sort()
        # The first repetition reads from disk what the others find in cache.
        values = [v for _, v in reps[1:]]
        rest[name] = values
        emit("probe", name, "first", s(reps[0][1]), unit="s")
        emit("probe", name, "median", s(statistics.median(values)),
             tuple(s(x) for x in stats.ci95(values, statistics.median, rng)), f"s, {len(values)} repetitions")
    return rest


def breakdown(fits, probe_values, rng):
    def diff(base, other):
        """Median of other minus median of base, with its interval."""
        value = statistics.median(probe_values[other]) - statistics.median(probe_values[base])
        ci = stats.ci95_difference(probe_values[base], probe_values[other], statistics.median, rng)
        return value, ci

    interpreter = statistics.median(probe_values["python_empty"])
    for stage, (import_name, load_name, offline_name) in STAGES.items():
        if stage not in fits:
            continue
        a, b, median_n = fits[stage]
        imports, imports_ci = diff("python_empty", import_name)
        model, model_ci = diff(import_name, offline_name)
        hub, hub_ci = diff(offline_name, load_name)
        loaded = statistics.median(probe_values[load_name])
        parts = [
            ("interpreter_start", interpreter, None),
            ("imports", imports, imports_ci),
            ("model_load_offline", model, model_ci),
            ("hub_check", hub, hub_ci),
            # What the probe cannot see: Prefect's task bookkeeping, the
            # database queries and the Qdrant set-up, the commit.
            ("rest_of_fixed", a - loaded, None),
            ("articles_at_median_n", b * median_n, None),
        ]
        total = a + b * median_n
        for name, value, ci in parts:
            emit("breakdown", stage, name, s(value), tuple(s(x) for x in ci) if ci else None,
                 f"s, {100 * value / total:.0f} % of {s(total)} s at N = {median_n:g}")


def main(prefix):
    rng = random.Random(stats.SEED)
    environment = read_environment(f"{prefix}_environment.txt")
    out.writerow(["view", "subject", "metric", "value", "ci95_low", "ci95_high", "unit"])

    runs, unknown = stage_runs(f"{prefix}_runs.csv")
    scaling("all_history", runs, unknown, rng)
    # The probe times the image deployed now, so the breakdown uses the runs
    # of that image only: older images had other library versions.
    since = environment.get("scheduler_started")
    if since:
        # Docker gives nanoseconds; the runs CSV compares as text to the second.
        since = since[:19] + "Z"
        runs, unknown = stage_runs(f"{prefix}_runs.csv", since)
        fits = scaling("current_image", runs, unknown, rng)
    else:
        fits = scaling("all_history_for_breakdown", runs, unknown, rng)
    breakdown(fits, probe(f"{prefix}_probe.csv", rng), rng)


if __name__ == "__main__":
    main(sys.argv[1])
