"""Experiment 04 probe. Runs inside the ETL image, one process per measurement.

Loads FinBERT exactly as production does (FinancialSentimentAnalyzer) and
classifies the same fixed texts REPS times, printing one CSV row per repetition.

    probe.py --mode production --reps 30 --texts FILE [--articles 64]
    probe.py --mode batched --batch-size 16 --reps 30 --texts FILE
    probe.py --describe --texts FILE

`production` reproduces the enrichment loop: analyze() once per text, as
app/ml/enrich_sentiment.py does. `batched` hands the pipeline the whole list
with a batch size. Each process starts cold, so its peak memory is its own.
"""
import argparse
import json
import sys
import time

from app.services.sentiment_analyzer import FinancialSentimentAnalyzer


def proc_status_mb(field):
    """VmRSS is resident memory now; VmHWM is the peak since the process began."""
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith(field + ":"):
                return int(line.split()[1]) / 1024
    raise KeyError(field)


def load_texts(path, count):
    with open(path, encoding="utf-8") as f:
        texts = [json.loads(line)["text"] for line in f if line.strip()]
    if len(texts) < count:
        raise SystemExit(f"{path} has {len(texts)} texts, {count} needed")
    return texts[:count]


def describe(texts_path):
    import torch
    import transformers

    analyzer = FinancialSentimentAnalyzer()
    texts = load_texts(texts_path, 1)
    tokenizer = analyzer.classifier.tokenizer
    with open(texts_path, encoding="utf-8") as f:
        all_texts = [json.loads(line)["text"] for line in f if line.strip()]
    tokens = sorted(len(tokenizer(t, truncation=True, max_length=512)["input_ids"]) for t in all_texts)
    print(f"torch: {torch.__version__}")
    print(f"transformers: {transformers.__version__}")
    print(f"torch_threads: {torch.get_num_threads()}")
    print(f"model: {analyzer.model_name}")
    print(f"model_revision: {getattr(analyzer.classifier.model.config, '_commit_hash', 'unknown')}")
    print(f"texts_in_file: {len(all_texts)}")
    print(f"tokens_median: {tokens[len(tokens) // 2]}")
    print(f"tokens_max: {tokens[-1]}")
    assert texts


def measure(mode, batch_size, reps, texts_path, articles):
    load_start = time.perf_counter()
    analyzer = FinancialSentimentAnalyzer()
    load_ms = (time.perf_counter() - load_start) * 1000
    load_rss = proc_status_mb("VmRSS")
    texts = load_texts(texts_path, articles)

    for rep in range(1, reps + 1):
        wall_start, cpu_start = time.perf_counter(), time.process_time()
        if mode == "production":
            for text in texts:
                analyzer.analyze(text)
        else:
            analyzer.classifier(texts, batch_size=batch_size)
        wall_ms = (time.perf_counter() - wall_start) * 1000
        # process_time counts every thread of the process, so cpu/wall shows
        # how many of the two cores the inference kept busy.
        cpu_ms = (time.process_time() - cpu_start) * 1000
        print(f"{mode},{batch_size},{rep},{articles},{wall_ms:.1f},{cpu_ms:.1f},"
              f"{proc_status_mb('VmRSS'):.1f},{proc_status_mb('VmHWM'):.1f},{load_ms:.0f},{load_rss:.1f}",
              flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--texts", required=True)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--mode", choices=["production", "batched"])
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--reps", type=int, default=30)
    parser.add_argument("--articles", type=int, default=64)
    args = parser.parse_args()

    if args.describe:
        describe(args.texts)
    elif args.mode:
        measure(args.mode, args.batch_size, args.reps, args.texts, args.articles)
    else:
        parser.error("either --describe or --mode is required")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
