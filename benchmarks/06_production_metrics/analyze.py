#!/usr/bin/env python3
"""Experiment 06: production resource use and server-side latency.

Usage: python3 analyze.py results/production_YYYYMMDD_HHMMSS

Prints one CSV, question,subject,metric,value,unit, with a block per question.
Samples of a time series are not independent repetitions, so nothing here is
bootstrapped: percentiles are nearest-rank over samples taken at a stated step.
"""
import csv
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import stats  # noqa: E402

MIB = 1024 * 1024
GIB = 1024 * MIB
DAY = 86400
# cAdvisor's housekeeping interval and the scrape interval are both 15 s.
SAMPLE_S = 15
# The scheduler's idle level is taken over the minutes before each ETL run.
IDLE_BEFORE_RUN = (600, 60)
# Starts closer than this belong to the same deploy.
DEPLOY_GAP = 600
RETENTION_DAYS = 180
SIZE_CAP = 10 * GIB  # retention.size=10GB; Prometheus reads GB as GiB.

out = csv.writer(sys.stdout)


def emit(question, subject, metric, value, unit=""):
    out.writerow([question, subject, metric, value, unit])


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def number(row, column):
    return float(row[column]) if row[column] != "" else None


def read_environment(path):
    environment = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if ": " in line and not line.startswith("#"):
            key, value = line.split(": ", 1)
            environment[key] = value
    return environment


# Question 1: resource use against the limits.

def containers(rows, host_memory, period_start):
    by_name = defaultdict(list)
    for row in rows:
        by_name[row["container"]].append(row)

    starts = []
    for name, series in sorted(by_name.items()):
        peak = max(series, key=lambda r: number(r, "working_set_bytes") or 0)
        peak_ws = number(peak, "working_set_bytes")
        peak_rss = max(number(r, "rss_bytes") or 0 for r in series)
        limits = {number(r, "limit_bytes") for r in series if number(r, "limit_bytes")}
        oom = max(number(r, "oom_events_total") or 0 for r in series)
        own_starts = sorted({number(r, "start_time") for r in series
                             if number(r, "start_time") and number(r, "start_time") >= period_start})
        starts += [(t, name) for t in own_starts]

        emit("1-containers", name, "peak_working_set", f"{peak_ws / MIB:.0f}", "MiB")
        emit("1-containers", name, "peak_working_set_at", iso(int(peak["timestamp"])))
        emit("1-containers", name, "peak_rss", f"{peak_rss / MIB:.0f}", "MiB")
        if limits:
            limit = max(limits)
            emit("1-containers", name, "limit", f"{limit / MIB:.0f}" + ("" if len(limits) == 1 else " (changed in period)"), "MiB")
            emit("1-containers", name, "peak_working_set_of_limit", f"{100 * peak_ws / limit:.1f}", "%")
        else:
            emit("1-containers", name, "limit", "none")
            emit("1-containers", name, "peak_working_set_of_host", f"{100 * peak_ws / host_memory:.1f}", "%")
        emit("1-containers", name, "oom_events", f"{oom:.0f}")
        emit("1-containers", name, "starts_in_period", len(own_starts))

    # Containers started within minutes of each other were recreated together
    # by a deploy. A start on its own is either a one-service deploy or a crash.
    starts.sort()
    groups = []
    for t, name in starts:
        if groups and t - groups[-1][-1][0] <= DEPLOY_GAP:
            groups[-1].append((t, name))
        else:
            groups.append([(t, name)])
    emit("1-starts", "all", "start_groups", len(groups))
    for group in groups:
        names = sorted({name.removeprefix("syndra_") for _, name in group})
        emit("1-starts", iso(int(group[0][0])), "containers_started", " ".join(names))


def overlaps_run(start, end, runs):
    return any(s <= end and start <= e for s, e in runs)


def host(rows, host_memory, etl_runs):
    rows = [r for r in rows if r["cpu_idle_seconds"] and r["cpu_total_seconds"]]
    busy = []  # (timestamp, fraction of both cores busy over the minute)
    for previous, current in zip(rows, rows[1:]):
        total = number(current, "cpu_total_seconds") - number(previous, "cpu_total_seconds")
        idle = number(current, "cpu_idle_seconds") - number(previous, "cpu_idle_seconds")
        if total > 0 and idle >= 0:  # a counter reset means a reboot: skip that minute
            busy.append((int(current["timestamp"]), 1 - idle / total))

    values = sorted(b for _, b in busy)
    emit("1-host", "cpu", "samples", len(values), "1-minute averages")
    emit("1-host", "cpu", "busy_median", f"{100 * stats.percentile(values, 50):.1f}", "% of 2 cores")
    emit("1-host", "cpu", "busy_p95", f"{100 * stats.percentile(values, 95):.1f}", "% of 2 cores")
    emit("1-host", "cpu", "busy_max", f"{100 * values[-1]:.1f}", "% of 2 cores")

    hourly = defaultdict(list)
    for t, b in busy:
        hourly[t // 3600].append(b)
    hours = sorted(statistics.fmean(v) for v in hourly.values() if len(v) >= 50)
    emit("1-host", "cpu", "hourly_mean_median", f"{100 * stats.percentile(hours, 50):.1f}", f"% of 2 cores, {len(hours)} hours")
    emit("1-host", "cpu", "hourly_mean_p95", f"{100 * stats.percentile(hours, 95):.1f}", f"% of 2 cores, {len(hours)} hours")

    # A sample stamped t averages the minute before it. The ETL runs about
    # 20 s, so a minute that overlaps a run is still mostly idle time.
    etl = sorted(b for t, b in busy if overlaps_run(t - 60, t, etl_runs))
    rest = sorted(b for t, b in busy if not overlaps_run(t - 60, t, etl_runs))
    emit("1-host", "cpu", "busy_median_etl_minutes", f"{100 * stats.percentile(etl, 50):.1f}", f"% of 2 cores, {len(etl)} minutes overlapping an ETL run")
    emit("1-host", "cpu", "busy_p95_etl_minutes", f"{100 * stats.percentile(etl, 95):.1f}", "% of 2 cores")
    emit("1-host", "cpu", "busy_median_other_minutes", f"{100 * stats.percentile(rest, 50):.1f}", "% of 2 cores")

    memory = [r for r in rows if r["mem_available_min_bytes"]]
    lowest = min(memory, key=lambda r: number(r, "mem_available_min_bytes"))
    available = number(lowest, "mem_available_min_bytes")
    emit("1-host", "memory", "total", f"{host_memory / MIB:.0f}", "MiB")
    emit("1-host", "memory", "available_min", f"{available / MIB:.0f}", "MiB")
    emit("1-host", "memory", "available_min_of_total", f"{100 * available / host_memory:.1f}", "%")
    emit("1-host", "memory", "available_min_at", iso(int(lowest["timestamp"])))
    emit("1-host", "memory", "available_median", f"{statistics.median(number(r, 'mem_available_min_bytes') for r in memory) / MIB:.0f}", "MiB")


def disk(rows):
    rows = [r for r in rows if r["fs_size_bytes"]]
    first, last = rows[0], rows[-1]
    used = [number(r, "fs_size_bytes") - number(r, "fs_free_bytes") for r in (first, last)]
    days = (int(last["timestamp"]) - int(first["timestamp"])) / DAY
    emit("1-host", "disk", "size", f"{number(last, 'fs_size_bytes') / GIB:.1f}", "GiB")
    emit("1-host", "disk", "used_first", f"{used[0] / GIB:.2f}", f"GiB at {iso(int(first['timestamp']))}")
    emit("1-host", "disk", "used_last", f"{used[1] / GIB:.2f}", f"GiB at {iso(int(last['timestamp']))}")
    emit("1-host", "disk", "growth_per_day", f"{(used[1] - used[0]) / days / MIB:.0f}", f"MiB/day over {days:.1f} days")
    emit("1-host", "disk", "available_last", f"{number(last, 'fs_avail_bytes') / GIB:.1f}", "GiB")
    boots = sorted({number(r, "host_boot_time") for r in rows if r["host_boot_time"]})
    emit("1-host", "reboots", "boot_times_seen", " ".join(iso(int(b)) for b in boots))


# Question 2: latency inside the API during the windows of experiment 05.

def bucket_interval(buckets, q):
    """(lower, upper] bound, in ms, of the bucket holding quantile q."""
    total = buckets[-1][1]
    lower = 0.0
    for le, count in buckets:
        if count / total >= q:
            return lower, le
        lower = le
    return lower, float("inf")


def bound(ms):
    return "inf" if ms == float("inf") else f"{ms:g}"


def server_latency(rows, client_summary):
    counts = defaultdict(lambda: defaultdict(float))
    requests = defaultdict(lambda: defaultdict(float))
    for row in rows:
        delta = float(row["value_at_end"]) - float(row["value_at_start"])
        if delta < 0:
            sys.exit(f"counter reset in {row['scenario']} run {row['run']}: the API restarted mid-window")
        if row["kind"] == "bucket":
            counts[row["scenario"]][row["key"]] += delta
        else:
            requests[row["scenario"]][row["key"]] += delta

    client = {r["scenario"]: r for r in read_csv(client_summary)} if client_summary else {}
    for scenario in counts:
        handlers = requests[scenario]
        test = max(handlers, key=handlers.get)
        other = sum(v for k, v in handlers.items() if k != test)
        emit("2-latency", scenario, "requests_test_endpoint", f"{handlers[test]:.0f}", test)
        emit("2-latency", scenario, "requests_other", f"{other:.0f}", "same windows, any other handler")

        buckets = sorted(((float("inf") if le == "+Inf" else float(le) * 1000, c)
                          for le, c in counts[scenario].items()))
        for p in (50, 95, 99):
            low, high = bucket_interval(buckets, p / 100)
            emit("2-latency", scenario, f"server_p{p}", f"({bound(low)}, {bound(high)}]", "ms, histogram bucket")
            if scenario in client:
                c = float(client[scenario][f"p{p}_ms"])
                # A difference of quantiles, not the quantile of a difference:
                # an approximation of where the network share lies.
                emit("2-latency", scenario, f"client_p{p}", f"{c:.1f}", "ms, from experiment 05")
                emit("2-latency", scenario, f"network_p{p}",
                     f"[{bound(max(0.0, c - high))}, {c - low:.1f})" if high != float("inf") else f"< {c - low:.1f}",
                     "ms, client minus server bucket")
        for le, c in buckets[:6]:
            emit("2-latency", scenario, f"share_le_{bound(le)}ms", f"{100 * c / buckets[-1][1]:.1f}", "%")


# Question 3: the scheduler during the ETL, against experiment 04.

def scheduler(rows, etl_runs, full_period_peak, inference_summary):
    samples = [(int(r["timestamp"]), number(r, "working_set_bytes"), number(r, "rss_bytes")) for r in rows]
    samples = [s for s in samples if None not in s]
    first, last = samples[0][0], samples[-1][0]

    peaks = {"working_set": [], "rss": []}
    idles = {"working_set": [], "rss": []}
    above_half = {"working_set": [], "rss": []}
    for start, end in etl_runs:
        if start - IDLE_BEFORE_RUN[0] < first or end + SAMPLE_S > last:
            continue  # the run is not fully inside the detailed series
        # A sample stamped t can describe memory up to SAMPLE_S earlier.
        during = [s for s in samples if start <= s[0] <= end + SAMPLE_S]
        before = [s for s in samples if start - IDLE_BEFORE_RUN[0] <= s[0] <= start - IDLE_BEFORE_RUN[1]]
        for i, metric in ((1, "working_set"), (2, "rss")):
            idle = statistics.median(s[i] for s in before)
            peak = max(s[i] for s in during)
            peaks[metric].append(peak)
            idles[metric].append(idle)
            above_half[metric].append(sum(1 for s in during if s[i] > idle + (peak - idle) / 2))

    emit("3-scheduler", "etl_runs", "count", len(peaks["rss"]), f"runs inside the detailed series, {SAMPLE_S} s samples")
    for metric in ("rss", "working_set"):
        p = sorted(peaks[metric])
        emit("3-scheduler", metric, "idle_median", f"{statistics.median(idles[metric]) / MIB:.0f}", "MiB, before each run")
        emit("3-scheduler", metric, "peak_median", f"{stats.percentile(p, 50) / MIB:.0f}", "MiB, per ETL run as sampled")
        emit("3-scheduler", metric, "peak_p90", f"{stats.percentile(p, 90) / MIB:.0f}", "MiB, per ETL run as sampled")
        emit("3-scheduler", metric, "peak_max", f"{p[-1] / MIB:.0f}", "MiB, detailed series")
        # The models stay loaded for a few seconds and memory is sampled every
        # 15 s, so most runs are sampled outside that moment.
        caught = sum(1 for v in p if v >= p[-1] / 2)
        emit("3-scheduler", metric, "runs_sampled_near_peak", f"{caught} of {len(p)}", "peak at least half the maximum")
        emit("3-scheduler", metric, "samples_above_half_peak_median", f"{statistics.median(above_half[metric]):.0f}", f"samples of {SAMPLE_S} s")
    emit("3-scheduler", "working_set", "peak_max_full_period", f"{full_period_peak['working_set'] / MIB:.0f}", "MiB, experiment 06 containers series")
    emit("3-scheduler", "rss", "peak_max_full_period", f"{full_period_peak['rss'] / MIB:.0f}", "MiB, experiment 06 containers series")

    if inference_summary:
        production = next(r for r in read_csv(inference_summary) if r["mode"] == "production")
        emit("3-scheduler", "experiment_04", "peak_rss_production_mode", production["peak_rss_mb"], "MiB, FinBERT alone, laptop")
        emit("3-scheduler", "experiment_04", "rss_after_model_load", production["load_rss_mb"], "MiB")


# Question 5: what keeps the CPU busy outside the ETL.

OBSERVABILITY = {"syndra_cadvisor", "syndra_node_exporter", "syndra_prometheus"}
# Modes in which the host is running code; iowait is waiting and steal is time
# the hypervisor gave to other machines, both outside our control.
RUNNING_MODES = ("user", "system", "nice", "irq", "softirq")
BLOCK_S = 900


def idle_cpu(rows, etl_runs, cores):
    blocks = defaultdict(dict)
    for row in rows:
        blocks[int(row["timestamp"])][row["source"]] = float(row["cpu_seconds"])
    # A block stamped t covers the 15 minutes before it. Blocks that touch an
    # ETL run, or that predate cAdvisor, are left out.
    quiet = {t: v for t, v in blocks.items()
             if "syndra_cadvisor" in v and not overlaps_run(t - BLOCK_S, t, etl_runs)}
    capacity = BLOCK_S * cores

    def report(subject, values, note=""):
        values = sorted(100 * v / capacity for v in values)
        emit("5-cpu", subject, "median", f"{stats.percentile(values, 50):.2f}", f"% of {cores:g} cores{note}")
        emit("5-cpu", subject, "p95", f"{stats.percentile(values, 95):.2f}", f"% of {cores:g} cores")

    emit("5-cpu", "blocks", "count", len(quiet), "15-minute blocks without an ETL run")
    names = sorted({s for v in quiet.values() for s in v if not s.startswith("host_")})
    for name in names:
        report(name, [v[name] for v in quiet.values() if name in v])

    def total(block, names_in):
        return sum(block.get(n, 0) for n in names_in)

    containers_all = [total(v, names) for v in quiet.values()]
    report("group_observability", [total(v, OBSERVABILITY) for v in quiet.values()], ", cadvisor + node_exporter + prometheus")
    report("group_syndra", [total(v, set(names) - OBSERVABILITY) for v in quiet.values()], ", every other container")
    report("all_containers", containers_all)
    running = [total(v, [f"host_{m}" for m in RUNNING_MODES]) for v in quiet.values()]
    report("host_running", running, ", user + system + nice + irq + softirq")
    # Docker, containerd, the kernel and anything else outside a container.
    report("host_outside_containers", [r - c for r, c in zip(running, containers_all)])
    report("host_steal", [v.get("host_steal", 0) for v in quiet.values()], ", taken by the hypervisor")
    report("host_iowait", [v.get("host_iowait", 0) for v in quiet.values()], ", waiting for disk")
    report("host_busy", [sum(x for k, x in v.items() if k.startswith("host_") and k != "host_idle")
                         for v in quiet.values()], ", every mode but idle, as in question 1")


# Question 4: size of the observability data.

def tsdb(rows, series_rows):
    rows = [r for r in rows if r["tsdb_blocks_bytes"]]
    last = rows[-1]
    t_last = int(last["timestamp"])
    on_disk = number(last, "tsdb_blocks_bytes") + number(last, "tsdb_wal_bytes")
    emit("4-tsdb", "now", "blocks", f"{number(last, 'tsdb_blocks_bytes') / MIB:.0f}", "MiB")
    emit("4-tsdb", "now", "wal", f"{number(last, 'tsdb_wal_bytes') / MIB:.0f}", "MiB")

    # Blocks grow in steps as Prometheus compacts, so the rate is a least-squares
    # slope over hourly samples, not the difference of two of them.
    for days in (7, 14):
        recent = [r for r in rows if int(r["timestamp"]) >= t_last - days * DAY]
        slope = statistics.linear_regression(
            [int(r["timestamp"]) / DAY for r in recent],
            [number(r, "tsdb_blocks_bytes") for r in recent]).slope
        emit("4-tsdb", f"last_{days}_days", "growth_per_day", f"{slope / MIB:.1f}", "MiB/day")
        if days == 14:
            projected = slope * RETENTION_DAYS + number(last, "tsdb_wal_bytes")
            emit("4-tsdb", "projection", "size_at_180_days", f"{projected / GIB:.2f}", "GiB, blocks plus current WAL")
            emit("4-tsdb", "projection", "share_of_size_cap", f"{100 * projected / SIZE_CAP:.0f}", "% of 10 GiB")
            emit("4-tsdb", "projection", "days_until_size_cap", f"{SIZE_CAP / slope:.0f}", "days, at this rate")

    head = sorted(number(r, "head_series_max") for r in rows if r["head_series_max"])
    emit("4-tsdb", "series", "head_series_max_in_period", f"{head[-1]:.0f}")
    for row in series_rows:
        emit("4-tsdb", "series_now", row["job"], row["series"])
    emit("4-tsdb", "now", "total_on_disk", f"{on_disk / MIB:.0f}", "MiB")


def main(prefix):
    environment = read_environment(f"{prefix}_environment.txt")
    host_memory = float(environment["host_memory_bytes"])
    period_start = datetime.fromisoformat(environment["period"].split(" to ")[0].replace("Z", "+00:00")).timestamp()
    here = Path(__file__).resolve().parent

    def sibling(key):
        value = environment.get(key, "none")
        return here / value if value not in ("none", "") else None

    container_rows = read_csv(f"{prefix}_containers.csv")
    etl_runs = [(int(r["start_epoch"]), int(r["end_epoch"])) for r in read_csv(f"{prefix}_etl_runs.csv")]
    scheduler_rows = [r for r in container_rows if r["container"] == "syndra_scheduler"]
    full_period_peak = {
        "working_set": max(number(r, "working_set_bytes") or 0 for r in scheduler_rows),
        "rss": max(number(r, "rss_bytes") or 0 for r in scheduler_rows),
    }

    out.writerow(["question", "subject", "metric", "value", "unit"])
    containers(container_rows, host_memory, period_start)
    host(read_csv(f"{prefix}_host.csv"), host_memory, etl_runs)
    disk(read_csv(f"{prefix}_storage.csv"))
    if Path(f"{prefix}_latency.csv").exists():
        server_latency(read_csv(f"{prefix}_latency.csv"), sibling("latency_client_summary"))
    scheduler(read_csv(f"{prefix}_scheduler.csv"), etl_runs, full_period_peak, sibling("inference_summary"))
    tsdb(read_csv(f"{prefix}_storage.csv"), read_csv(f"{prefix}_series.csv"))
    if Path(f"{prefix}_cpu.csv").exists():
        idle_cpu(read_csv(f"{prefix}_cpu.csv"), etl_runs, float(environment["host_cores"]))


if __name__ == "__main__":
    main(sys.argv[1])
