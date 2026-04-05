## ADR 004: Custom Scraping (Scrapy) vs. Third-Party News APIs

**Context:** The system requires a constant flow of raw news data. I evaluated commercial News APIs (GNews, NewsAPI) versus building a custom web scraper. The core value of Syndra relies on running local LLMs over the entire article text to generate custom embeddings. Third-party APIs usually restrict payload size.

**Decision:** Implement a custom extraction engine using Scrapy, initially targeting standard RSS feeds to guarantee structured data, with the capability to download full HTML payloads.

**Consequences:** 100% Data Ownership, zero operational cost, and guaranteed access to full-text DOM elements. Requires strict rate-limiting to obey robots.txt and avoid IP bans.
