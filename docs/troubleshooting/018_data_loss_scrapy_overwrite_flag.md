## Incident 018: Data Loss by Overwrite in Multi-Source Scrapy Ingestion

**Symptom:** After enabling the BYOS (Bring Your Own Source) architecture with multiple RSS feeds in `feeds.json`, only the articles from the **last** feed in the list were arriving in the database. All previously scraped feeds were missing.

**Root Cause:** The pipeline orchestration script (`pipeline.py`) iterated over each feed entry in `feeds.json` and invoked the Scrapy CLI sequentially. The command used the `-O` flag (uppercase), which **overwrites** the output file on each invocation. As a result, each subsequent spider run destroyed the output of the previous one, and only the final feed's articles survived to the database loading stage.

**Resolution:** Changed the Scrapy CLI flag from `-O` (overwrite) to `-o` (lowercase, append):
```diff
- subprocess.run(["scrapy", "crawl", "rss", "-O", output_file, ...])
+ subprocess.run(["scrapy", "crawl", "rss", "-o", output_file, ...])
```
This concatenates all extracted articles from every configured feed into a single JSON output file, which is then loaded as a unified batch into the Bronze layer.

**Key Lesson:** Scrapy's `-O` and `-o` flags have drastically different semantics. In any multi-pass extraction loop, **always** use lowercase `-o` (append). The uppercase variant should only be used for single-shot, isolated spider runs.
