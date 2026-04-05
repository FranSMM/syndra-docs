## Incident 004: `ModuleNotFoundError` during ETL script execution

**Symptom:** Running `python app/scraper/load_to_db.py` inside Docker throws `ModuleNotFoundError: No module named 'app'`.

**Root Cause:** Executing a Python script via its direct file path alters `sys.path` to start at the script's specific directory, breaking absolute imports from the root package.

**Resolution Applied:** Executed the script using Python's native module flag (`-m`) from the root working directory (`/code`).
```bash
python -m app.scraper.load_to_db
```
