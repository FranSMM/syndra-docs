"""Statistics shared by the analyze.py scripts.

Standard library only, so any python3 can rerun an analysis without installing
anything. Every random draw goes through an explicitly seeded generator.
"""
import math

SEED = 2026
RESAMPLES = 10_000


def percentile(sorted_values, p):
    """Nearest-rank percentile: always an observed value, never an interpolation."""
    k = max(1, math.ceil(p / 100 * len(sorted_values)))
    return sorted_values[k - 1]


def _interval(estimates):
    estimates.sort()
    return estimates[int(0.025 * len(estimates))], estimates[int(0.975 * len(estimates)) - 1]


def ci95(values, statistic, rng, resamples=RESAMPLES):
    """95 % bootstrap confidence interval of statistic(values)."""
    n = len(values)
    return _interval([statistic(rng.choices(values, k=n)) for _ in range(resamples)])


def ci95_percentiles(values, ps, rng, resamples=RESAMPLES):
    """Bootstrap intervals for several percentiles, sharing each resample."""
    n = len(values)
    estimates = {p: [] for p in ps}
    for _ in range(resamples):
        sample = sorted(rng.choices(values, k=n))
        for p in ps:
            estimates[p].append(percentile(sample, p))
    return {p: _interval(estimates[p]) for p in ps}


def ci95_difference(a, b, statistic, rng, resamples=RESAMPLES):
    """Bootstrap interval of statistic(b) - statistic(a), resampling each group."""
    na, nb = len(a), len(b)
    return _interval([
        statistic(rng.choices(b, k=nb)) - statistic(rng.choices(a, k=na))
        for _ in range(resamples)
    ])
