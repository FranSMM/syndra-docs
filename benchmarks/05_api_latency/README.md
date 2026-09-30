# 05 - API latency at the load of one client

**Question:** how long does the API take to answer a request under normal use, with the cache warm and with the cache cold?

**Why latency and not capacity:** at 0.4 requests/s the experiment stays well under the 100 requests/min per-key limit and adds the load of a single user, so it can run against production. Finding the rate at which the API degrades would mean pushing it until it fails, which cannot be done on the production VPS without breaking the service; it would need a clone of the VPS and is left as future work.

**What is measured:** end-to-end latency from the client, through Cloudflare and Caddy to the API and back. It is what a customer sees, so it depends on where the client runs: record it in `CLIENT_LABEL`.

| Scenario | Requests | Cache |
|---|---|---|
| `sentiment_warm` | `/api/v1/sentiment/NVDA`, always the same | Hit, except one miss every 300 s TTL |
| `sentiment_cold` | the 141 tickers of `tickers.txt`, in turn | Miss: a full cycle takes 352 s, past the 300 s TTL |
| `search_warm` | `/api/v1/search/semantic`, one fixed query | Hit, except one miss every 300 s TTL |
| `search_cold` | ticker + topic queries, never repeated in a session | Miss: embedding on CPU plus Qdrant search |

Every ticker in `tickers.txt` has at least 20 articles, the endpoint's default `limit`, so every cold sentiment request does the same amount of work.

**Protocol:** open-loop load with [vegeta](https://github.com/tsenart/vegeta) 12.13.0: requests leave at a fixed rate whether or not earlier ones have answered, so a slow server cannot hide its latency by slowing the client down. 3 runs per scenario, 10 minutes each at 0.4/s (240 requests per run), with runs of different scenarios interleaved in time. Between runs there is a 310 s pause so no run inherits the previous one's cache, and each run waits until it fits between :05 and :55, away from the ETL that runs at :58 on the same two cores. A full session takes about 3 to 3.5 hours.

**Setup, once:**

1. Create a dedicated API key for the benchmark, as a trial so it expires on its own: `docker exec syndra_api python -m app.scripts.provision_client benchmark_latency --trial 2` on the VPS. Never use the demo key: its limit is shared and the demo would get 429s during the run.
2. Add `SYNDRA_BENCH_KEY=<the raw key>` to the root `.env`, which git ignores. Exporting it in the shell works too, for a single session. The script passes it as a request header and never writes it to the results.

**Run** (from WSL):

    CLIENT_LABEL=laptop-wsl-home ./measure.sh
    python3 analyze.py results/latency_YYYYMMDD_HHMMSS.csv > results/latency_YYYYMMDD_HHMMSS_summary.csv

The script downloads vegeta on first use and checks its SHA-256 against the value pinned in the script.

**Statistics:** nearest-rank percentiles (always an observed value, never an interpolation), p50, p90, p95 and p99, each with a 95 % bootstrap confidence interval (10,000 resamples, seed 2026). Non-200 responses are counted as errors and excluded from the percentiles. The first request of each run pays the TLS handshake and is reported apart. With 720 requests per scenario the p99 rests on about 7 observations: read its interval, not only its value.

**Side effects in production:** 2,880 synthetic requests over the session, all under one test key. They enter the HTTP metrics in Prometheus; the environment file records every run window so they can be excluded from the Chapter 4 traffic figures. Revoke the test key afterwards.

**Regenerating `tickers.txt`:** see the query in its header. It only changes if the corpus changes, and a new list means the cold scenario is no longer the same experiment: keep the file of the run being quoted.
