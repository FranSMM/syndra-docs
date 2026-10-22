# ADR 037: Publication Date Normalisation at the Bronze to Silver Boundary

**Status:** Accepted
**Relates to:** [ADR 036](./036_rfc822_date_normalisation_byos.md), [ADR 024](./024_medallion_architecture_bronze_silver_separation.md), [ADR 033](./033_late_deduplication_serving_layer.md)

## Context

ADR 036 normalised dates on the way into Bronze. This ADR covers the next boundary: turning that stored string into `Article.published_at` in Silver, a naive UTC column. Two defects lived there, and neither was visible.

**The offset was discarded, not converted.** The enrichment did `datetime.fromisoformat(raw).replace(tzinfo=None)`, so `07:00:00-05:00` was stored as 07:00 instead of 12:00. It went unseen because of the corpus composition on 15/09/2026:

| Source | Articles | Emits | Affected |
|---|---|---|---|
| `global_finance_rss` | 69,686 | `Z` | No |
| `bbc_business` | 295 | `Z` | No |
| `sec_press_releases` | 39 | `-04:00` / `-05:00` | Yes |

With a UTC feed, dropping the offset and converting it give the same result. Only 39 of 70,020 articles were wrong, but the error mattered: the late deduplication (ADR 033) compares timestamps within a 3 h window, and a 4 to 5 h error is wider than the whole window.

**The feed can be wrong about its own dates.** The SEC republishes 1990s press releases stamped with the current year. The Bronze payload already carried these dates, so it is source data, not a parsing bug. Two were dated in the future (release `97-114` stored as 2026-12-16, `97-99` as 2026-11-05), which made the source's freshness metric negative (−2,203 h). A third (`99-110`, stored as 2026-09-07) is dated in the past and passes any generic check.

## Decision

1. **Convert the offset to UTC** before dropping `tzinfo`. A naive value is assumed UTC, as in ADR 036.
2. **Reject dates that cannot be true:** a publication date more than one hour after the Bronze row's `created_at`. The hour absorbs publisher clock drift.
3. **A rejected date becomes NULL, never an invented one.** Everything downstream trusts the timestamp; NULL only removes the article from time-window queries.

The generic rules live in `app/core/dates.py` and know nothing about any publisher. The SEC rule, that the release number in the URL carries the real year, lives in `app/core/source_rules.py`. Keeping the two apart means the generic rules stay trustworthy, and source coupling shows up as an import instead of an `if` inside the enrichment loop. A source rule only rejects on evidence: a URL without a release number never discards an article.

## Alternatives rejected

- **Migrate the column to `timestamptz`.** It fixes the storage, not the input: the offset would still have to be parsed correctly, and every query and DTO assumes naive UTC. Larger change, same fix.
- **Clamp future dates to `now()`.** It invents a timestamp that looks valid and is wrong, which is worse than a missing one.
- **Discard the whole article.** The text, sentiment and tickers are correct; only the date is not. NULL keeps the article and drops only the unreliable field.

## Consequences

- **Backfill.** `app/scripts/backfill_published_at.py` recomputes Silver from the untouched Bronze string. On 16/09/2026: 37 timestamps corrected, 3 set to NULL, 69,980 unchanged. A second pass changed nothing. 36 of the 37 moved +4 h, not +5 h, because the SEC observes daylight saving: a fixed "add five hours" migration would have broken 36 of 37.
- **Bronze stays immutable.** Only Silver is rewritten.
- **New metric:** `syndra_articles_without_publication_date{source}` counts the NULLs, so a feed that starts emitting impossible dates shows up instead of disappearing silently.
- **Open:** past-dated reprints are only caught where a source rule exists. Past three or four rules, sources should declare their date semantics in `feeds.json` instead.
