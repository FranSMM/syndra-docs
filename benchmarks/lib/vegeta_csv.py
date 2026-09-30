#!/usr/bin/env python3
"""Converts `vegeta encode --to csv` output on stdin into the benchmark CSV.

    vegeta_csv.py --base URL [--field name=value ...] < raw.csv >> results.csv

Each row gets the fixed fields first (scenario, run, rate...), then
seq, timestamp, code, latency_ms, bytes_in, error, url. Response bodies and
headers are dropped: they are not needed and would inflate the raw data. The
URL loses its base, so the host never appears in the results.
"""
import argparse
import csv
import sys

# Column order of vegeta's CSV encoder.
VEGETA_COLUMNS = ["timestamp", "code", "latency_ns", "bytes_out", "bytes_in", "error",
                  "body_b64", "attack", "seq", "method", "url", "headers_b64"]
OUTPUT_COLUMNS = ["seq", "timestamp", "code", "latency_ms", "bytes_in", "error", "url"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", required=True)
    parser.add_argument("--field", action="append", default=[], help="name=value added to every row")
    parser.add_argument("--header", action="store_true", help="print the header row and exit")
    args = parser.parse_args()

    fixed = [f.split("=", 1) for f in args.field]
    writer = csv.writer(sys.stdout, lineterminator="\n")
    if args.header:
        writer.writerow([name for name, _ in fixed] + OUTPUT_COLUMNS)
        return

    base = args.base.rstrip("/")
    for raw in csv.reader(sys.stdin):
        row = dict(zip(VEGETA_COLUMNS, raw))
        writer.writerow([value for _, value in fixed] + [
            row["seq"],
            row["timestamp"],
            row["code"],
            f"{int(row['latency_ns']) / 1e6:.3f}",
            row["bytes_in"],
            row["error"],
            row["url"].replace(base, "", 1),
        ])


if __name__ == "__main__":
    main()
