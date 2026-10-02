## Playbook 8: HuggingFace Model Management (Cache and VRAM)

Syndra uses two models from the Hugging Face Hub: `ProsusAI/finbert` for sentiment (about 420MB) and `sentence-transformers/all-MiniLM-L6-v2` for embeddings (about 90MB).

* **Physical Location:** both models are part of the ETL image, under `/models_cache` (`HF_HOME`). They are downloaded once, at build time, at the revisions pinned in `backend/Dockerfile`. The API and the scheduler run the same image, so they load the same files.

* **No Hub access at run time:** the image sets `HF_HUB_OFFLINE=1` ([ADR 042](../adr/042_models_pinned_and_offline.md)). A load that needs a file the image does not have fails at once with an error, instead of downloading it. The build loads both models offline right after downloading them, so a missing file fails the build before it can reach production.

* **Checking a container:**

    ```bash
    docker exec syndra_scheduler sh -c 'echo HF_HUB_OFFLINE=$HF_HUB_OFFLINE; ls /models_cache/hub'
    ```

* **Weights Update:** a model only changes when its revision changes.

    1. Take the new commit from the model's page on the Hub (Files and versions, History).
    2. Change `FINBERT_REVISION` or `EMBEDDING_MODEL_REVISION` in `backend/Dockerfile` and the matching default in `backend/app/core/config.py`.
    3. Rebuild and deploy.

    A new FinBERT revision only scores new articles: the sentiment already stored keeps the old model's scores. Compare both revisions on a sample before deploying. A new MiniLM revision changes the vector space, so every vector in Qdrant has to be re-indexed, or old and new vectors stop being comparable.

* **VRAM Monitoring (NVIDIA):** During the execution of the enrichment node, it is advisable to open a second terminal and run `watch -n 1 nvidia-smi`. This allows monitoring the peak memory consumption of the GTX 1650 Ti and ensures that the `batch_size` (currently 200) does not exceed the available 4GB.
