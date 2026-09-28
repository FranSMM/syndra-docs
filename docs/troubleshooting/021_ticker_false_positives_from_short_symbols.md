## Incident 021: Ticker False Positives from Short Symbols and Untrimmed Aliases

**Symptom:** `GET /api/v1/sentiment/A` returns articles about anything containing the English article "a". `/sentiment/S` returns every article mentioning "U.S." or "S&P". `/sentiment/AI` returns the entire artificial-intelligence news cycle rather than C3.ai. The responses are well-formed and the sentiment scores are correct, they are simply about the wrong companies.

**How it surfaced:** while measuring cross-source duplication after adding BBC and SEC feeds (ADR 036), the single candidate duplicate pair turned out to be two unrelated articles matched to each other because both carried ticker `A`, one from "**A** colleague", the other from "**A**I".

**Scope, measured on the production corpus (58,426 articles):**

| | |
|---|---|
| Articles carrying at least one ticker | 34,058 |
| Attachments from 1-2 character symbols | 29.4 % of all attachments |
| Articles whose *only* tickers are 1-2 chars | 7,451 |

Worst offenders by volume: `AI` 3,488 articles (6.0 % of the corpus), `A` 1,819, `S` 1,218, `BLSH` 896, `DOW` 663, `U` 639, `P` 624.

**Root cause: two independent defects.**

1. **The bare symbol was always registered as a keyword.** `_initialize` appended the ticker to its own alias list, so one- and two-character symbols matched ordinary English. `U.S.` yields `U` and `S`; `S&P` yields `S` and `P`; `A` matches the article; `CD` matches "CD rates". The *company-name* aliases were never the problem: "Agilent Technologies" is unambiguous.

2. **Two aliases are ordinary vocabulary.** `BLSH` (Bullish Global) ships the alias `"Bullish"` and matched every "analysts turn bullish" headline. `DOW` ships `"Dow"` and matched the index rather than Dow Inc. These are the only three such entries in the dictionary; both were found by measurement, not guessed.

**A third defect found while fixing the first two.** Withholding bare short symbols initially made 69 companies unfindable: Altria, Zoom, DuPont, Agilent, Broadridge among them. Their aliases are derived upstream by truncating "X, Inc." and therefore end in a comma: `"Agilent Technologies,"`. FlashText matches exactly, so that alias never fired on the far more common "Agilent Technologies beat expectations". 2,997 tickers had *every* alias ending in punctuation.

**Resolution.**

- Bare symbols shorter than three characters are no longer registered as keywords. Their company names are, so a genuine mention still resolves.
- The three common-word aliases are withheld.
- Every alias is additionally registered in a trimmed form, adding 2,447 usable aliases and repairing the 69 short tickers that the first change would otherwise have broken.

**Verification.** Simulated against 4,000 random production headlines before changing the code:

| | |
|---|---|
| Unchanged | 3,116 |
| Changed | 884 |
| Lost every ticker | 464 (11.6 %) |

Of the 884 removed attachments, 847 were `AI`, `A`, `S`, `P`, `BLSH`, `U` or `DOW`. Spot-checked headlines that lost all tickers: "The Smartest S&P 500 ETF to Buy", "U.A.E. Asks U.S. for a Wartime Financial Lifeline", "Best CD rates today", carry no company reference at all.

**The accepted cost.** A one- or two-character ticker mentioned *only* as a bare symbol, with the company never named, is no longer matched: `"Market Digest: MKL, AVY, FISV, GT, XEL"` loses `GT`. Measured as rare, `GT` did not reach the top fifteen removed symbols, and taken deliberately in exchange for removing the noise. `tests/test_ticker_extractor.py` asserts this loss explicitly so it stays a recorded trade rather than a regression somebody later "fixes" by reverting.

## What the first fix missed, found by inspecting the result

The first backfill was run and the corpus re-inspected rather than declared done. Three further problems surfaced.

### A regression the fix itself introduced: `NDAQ`

`NDAQ` went from absent in the top twenty to **673 articles**: every one of them about the Nasdaq *index*: "Dow hits record, S&P 500, Nasdaq slip". The stored alias is `"Nasdaq,"`; with the trailing comma it never matched prose, and trimming it to `"Nasdaq"` switched it on.

The guard that should have caught it was written and did nothing. `STOP_ALIASES` was compared against the **raw** alias, so `"Nasdaq,"` never equalled `"nasdaq"`: the stop list was silently inert for exactly the aliases the trimming was about to activate. It now compares the normalised form, which is what actually gets registered.

### Warrants and preferred series absorbing company news

"Morgan Stanley Maintains Overweight Rating on Aon plc" was tagging `MS-PL`, a preferred series, instead of `MS`. 728 attachments (2.0 %) came from hyphenated tickers: `MS-PL` 330, `ACHR-WT` 53, `JOBY-WT` 34, plus `-P*` series. 462 such tickers are now excluded. Ordinary share classes such as `BRK.B` are genuine securities and stay.

### Qdrant and Postgres disagreeing

`backfill_vectors` is incremental: it skips anything flagged `is_vectorized`, so after the Silver Layer was corrected it found nothing to do and every point kept its old payload. The two stores then answered differently for the same symbol:

| | Qdrant | Postgres |
|---|---|---|
| `AI` | 1,145 | 0 |
| `A` | 429 | 8 |
| `MS-PL` | 318 | 0 |

`/sentiment/AI` returned nothing while `/search/semantic?ticker=AI` still returned 1,145 results. Fixed by `app/scripts/resync_vector_payloads.py`, which rewrites payloads only: the vectors embed title and description, neither of which changed, so re-encoding would have cost hours to produce identical vectors.

## Result

Measured on the production corpus, before and after:

| | Before | After |
|---|---|---|
| `AI` | 3,750 | 0 |
| `A` | 1,903 | 8 |
| `BLSH` | 953 | 2 |
| `DOW` | 663 | 11 |
| `NDAQ` | 673 | 6 |
| `MS-PL` | 330 | 0 |
| Attachments from 1-2 char symbols | 13,134 (29.6 %) | 2,635 (7.5 %) |

Legitimate attributions **rose** rather than merely surviving: `NVDA` 1,240 → 1,340, `AAPL` 588 → 607, because 2,363 trimmed aliases made company names matchable that never were. The top ten is now NVDA, MU, AMZN, AAPL, TSLA, META, MSFT, GOOGL, INTC, AMD.

Backups taken before the destructive pass: `~/backups/pre_ticker_backfill_20260824_182700.sql`.

## Still open: duplicate listings

`GOOGN` and `GOOGL` both carry the alias `"Alphabet"`, so every Alphabet article receives both. This is dictionary duplication across listings rather than a matching defect, and needs a rule for preferring the primary listing, which the data does not currently mark. Left alone deliberately; it produces a redundant tag, not a wrong one.

**Architectural lesson.** The extractor was never wrong by its own rules: FlashText found real symbols belonging to real companies, exactly as instructed. The defect was in what it was told to look for. A dictionary assembled from an authoritative source (SEC registrants) is not automatically a good matching vocabulary: authority guarantees the symbols exist, not that they are unambiguous in prose. Any exact-match entity extractor needs its vocabulary audited against the *text it will actually see*, and the audit has to be a measurement, because at 11,119 entries nobody spots `BLSH → "Bullish"` by reading.

**Second lesson, from the `NDAQ` regression.** Widening a matcher's vocabulary is not a safe operation, and the guard against it can be present and inert. `STOP_ALIASES` existed, was correct in intent, and compared the wrong string, so it protected nothing precisely where protection was needed. The check that caught this was re-measuring the corpus *after* the fix rather than trusting the test suite, which passed throughout. Tests confirm the cases you thought of; only the data shows the ones you did not.

**Third lesson: a correction is not complete until every store agrees.** The Silver Layer is the source of truth, but Qdrant holds a denormalised copy of `tickers` in its payloads and its backfill is deliberately incremental. Any change to enrichment output has to answer "which other stores hold a copy of this?", here the answer was one, and missing it would have left the two public endpoints contradicting each other indefinitely, with nothing failing loudly enough to notice.
