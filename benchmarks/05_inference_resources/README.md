# 05 · Inference resources

**Question:** how much CPU and memory does FinBERT use per batch, and where is the VPS ceiling?

**Status:** pending. Follow the template of [01_subprocess_startup](../01_subprocess_startup/) and the rules in the [index](../README.md): measuring and analysing kept separate, 30 repetitions, the first one reported apart, a fixed seed, and raw data under `results/`.

**What to measure:** memory and CPU against batch size. The cAdvisor history already gives the peak and the mean in production (Phase 6.2); what is missing is the curve against batch size, taken locally and contrasted with the observed peak.
