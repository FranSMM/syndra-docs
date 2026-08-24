# ADR 036: RFC 822 Date Normalisation — the precondition for BYOS

**Status:** Accepted
**Relates to:** [ADR 029](./029_byos_flashtext_source_agnostic_ingestion.md) (BYOS), [ADR 003](./003_postgresql_as_the_primary_database.md)

## Context

The BYOS thesis — the client brings their own sources, Syndra ingests them — had never actually been exercised. After eight months of production the pipeline had ingested 56,064 articles, **100 % of them from a single feed**. The roadmap treated this as a configuration gap: "add three more URLs to `feeds.json`, ~2h".

It was not a configuration gap. Measured against the real `ScrapedArticle` schema, running inside the production container:

| Feed | Items accepted |
|---|---|
| Yahoo Finance (the incumbent) | 45 / 45 |
| MarketWatch | 0 / 10 |
| BBC Business | 0 / 52 |
| Financial Times | 0 / 25 |
| SEC Press Releases | 0 / 25 |
| Seeking Alpha | 0 / 30 |
| The Guardian Business | 0 / 41 |
| Cointelegraph | 0 / 30 |

Every rejection was the same field: `published_at`.

**Root cause.** RSS 2.0 mandates RFC 822 dates (`Wed, 12 Aug 2026 19:36:21 -0400`). Pydantic v2 parses ISO 8601 and does not accept RFC 822. The spider caught the resulting `ValidationError`, logged it, and continued — so a standards-compliant feed produced **zero articles while the pipeline reported success**.

Yahoo Finance was never chosen for being the best source. It emits ISO 8601 rather than RFC 822, which made it the only feed in the candidate set that could ever have worked. The single-source dataset was an accident of format compatibility, not a decision.

## Decision

Normalise `<pubDate>` in the spider before handing it to Pydantic: parse RFC 822 with `email.utils.parsedate_to_datetime`, emit ISO 8601, and pass anything unrecognised through untouched so ISO-emitting feeds are unaffected.

A date with no offset is assumed UTC. RFC 822 permits omitting it; the alternative is discarding the item, and the storage layer already treats timestamps as naive UTC. Genuinely unparseable input is **not** coerced — it is passed through and rejected by the schema, because a fabricated timestamp is worse than a missing article.

Two defects surfaced while verifying this and are fixed in the same change:

- **Untrimmed fields.** Extraction used `.get()` with no `.strip()`. The SEC indents its XML, so titles arrived with leading whitespace — which would reach the API verbatim and distort the `SequenceMatcher` ratio the late deduplication depends on (ADR 033).
- **Anonymous user agent.** The SEC requires automated clients to identify themselves with a contact address and throttles those that do not. The agent string now carries one.

## Sources added

| Source | `source_type` | Why this one |
|---|---|---|
| `bbc_business` | `rss_feed` | 53 articles, refreshed hourly, different geography and editorial register from the incumbent |
| `sec_press_releases` | `regulatory` | A **regulator, not a publisher**. Structurally a different channel, which is what makes the BYOS claim demonstrable rather than "three more news aggregators". US Government material, so no ToS exposure. Activates the `source_type` column, until now uniformly `rss_feed`. |

Verified end-to-end with the real spider against production: Yahoo 49, BBC 53, SEC 25.

## Alternatives rejected

- **Loosen the schema** to accept any string and parse downstream. Rejected: it moves a boundary check past the boundary, which is the opposite of the fail-fast principle the ingestion layer is built on.
- **A `dateutil` dependency.** `parsedate_to_datetime` is standard library and handles the one format RSS actually mandates. A dependency for this would be unearned.
- **Feedspot's "top financial RSS feeds" directory.** Surveyed and rejected on measurement: it ranks by human readership, not machine-readability. Several entries are Atom (no `<item>`), one advertises timestamps 62 days in the future, several are weekly newsletters, and the blogs mention no companies at all — `abnormalreturns` yielded tickers in 0 of 14 items. An article with no ticker is ingested, scored and indexed, then never surfaces in the ticker-keyed API: cost without reach.

## Consequences

- **Positive:** BYOS becomes demonstrable. Any standards-compliant RSS feed is now ingestible, which is what the architecture always claimed.
- **Positive:** The `source_type` column carries a real distinction for the first time.
- **Measured, not assumed — cross-source duplication does not occur with these sources.** This ADR originally warned that multi-source ingestion would expose the same story reported by several outlets, and that ADR 033's deduplication was built for same-source reprints. That was a reasonable worry and it is wrong here. Over a live snapshot of 128 articles:

  | | |
  |---|---|
  | cross-source pairs compared | 5,225 |
  | pairs scoring ≥ 0.85 (would be deduplicated) | 0 |
  | pairs scoring ≥ 0.55 at all | 0 |
  | pairs sharing a company within 24h | 1 |

  The single shared-company pair was a **false positive from ticker extraction**, not a duplicate: two unrelated articles both matched ticker `A` because one contained "**A** colleague" and the other "**A**I".

  The reason is the source selection itself. US market aggregation, UK business reporting and US regulatory enforcement barely overlap in subject matter. No change was made, because there was nothing to fix.

  **The condition under which this returns:** adding a second source of the same kind — CNBC or MarketWatch alongside Yahoo, both US market wires — would put genuinely overlapping coverage into the corpus. Re-run the measurement before adding one, rather than assuming either outcome.
- **Open:** Ticker extraction produces false positives on one- and two-letter symbols — `U.S.` yields `U` and `S`, `S&P` yields `S` and `P`, and `AI` matches every article about artificial intelligence. This predates the change and affects the existing corpus. Tracked separately; adding sources increases the volume flowing through it but is not its cause.
