# 04 - API load

**Question:** what latency and error rate does the API sustain with a single worker before it degrades?

**Status:** pending. Follow the template of [01_subprocess_startup](../01_subprocess_startup/) and the rules in the [index](../README.md): measuring and analysing kept separate, 30 repetitions, the first one reported apart, a fixed seed, and raw data under `results/`.

**What to measure:** latency percentiles and errors per concurrency level against the throwaway stack that `run-integration-tests.sh` brings up. Never against production: it injects synthetic traffic into the Chapter 4 metrics and inserts test API keys.

Latency under normal use, which can run against production at a low rate, is [06_api_latency](../06_api_latency/). This experiment is about capacity.
