## Incident 007: Anti-Bot Blocking in RSS extraction (Yahoo Finance)

**Symptom:** The Scrapy pipeline executed successfully (Exit Code 0) but the log showed `scraped 0 items`. When running in debug mode, the following was observed: `DEBUG: Forbidden by robots.txt`

**Root Cause:** Scrapy obeys the target domains' `robots.txt` file by default. Yahoo Finance actively blocks generic scraping User-Agents

**Resolution Applied:** Modified the global Scrapy configuration file (settings.py):
1. `ROBOTSTXT_OBEY = False`
2. `USER_AGENT` was spoofed to mimic a standard Chrome browser on Windows.
