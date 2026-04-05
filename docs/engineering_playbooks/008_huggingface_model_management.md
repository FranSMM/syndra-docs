## Playbook 8: HuggingFace Model Management (Cache and VRAM)

The ProsusAI/finbert model weighs approximately 420MB.

* **Physical Location:** The model is persisted on the host under `./data/huggingface/hub/`.

* **Weights Update:** To force the download of a more recent version of a model (clearing the cache):

    ```bash
    rm -rf ./data/huggingface/hub/models--ProsusAI--finbert/
    ```

* **VRAM Monitoring (NVIDIA):** During the execution of the enrichment node, it is advisable to open a second terminal and run `watch -n 1 nvidia-smi`. This allows monitoring the peak memory consumption of the GTX 1650 Ti and ensures that the `batch_size` (currently 200) does not exceed the available 4GB.
