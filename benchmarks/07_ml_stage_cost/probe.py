"""Times the fixed costs every ML stage pays: interpreter start, imports and
model loading, each in a fresh process like the subprocess of every ETL run.

Runs inside the scheduler container, fed through stdin by measure.sh
(`python - MEASUREMENT REPS`), and prints one CSV row per repetition.
Nothing is written: the container already sets PYTHONDONTWRITEBYTECODE.
"""
import os
import subprocess
import sys
import time

SENTIMENT_LOAD = (
    "import app.ml.enrich_sentiment as stage; "
    "stage.FinancialSentimentAnalyzer(); stage.TickerExtractor()"
)
VECTOR_LOAD = (
    "import app.backfill_vectors; "
    "from app.services.embedding_service import get_embedding_engine; get_embedding_engine()"
)
# Production loads with the Hugging Face hub reachable; offline the same load
# skips the hub's freshness check, so the difference is that check.
OFFLINE = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}

MEASUREMENTS = {
    "python_empty": ("pass", {}),
    "import_torch_transformers": ("import torch, transformers", {}),
    "import_sentiment_stage": ("import app.ml.enrich_sentiment", {}),
    "load_sentiment_models": (SENTIMENT_LOAD, {}),
    "load_sentiment_models_offline": (SENTIMENT_LOAD, OFFLINE),
    "import_vector_stage": ("import app.backfill_vectors", {}),
    "load_vector_model": (VECTOR_LOAD, {}),
    "load_vector_model_offline": (VECTOR_LOAD, OFFLINE),
}


def main(name, reps):
    code, extra_env = MEASUREMENTS[name]
    env = {**os.environ, **extra_env}
    for rep in range(1, reps + 1):
        start = time.perf_counter()
        subprocess.run([sys.executable, "-c", code], cwd="/code", env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{name},{rep},{(time.perf_counter() - start) * 1000:.1f}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
