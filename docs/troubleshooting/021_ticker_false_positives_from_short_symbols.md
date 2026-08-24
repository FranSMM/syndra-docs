## Incident 021: Ticker False Positives from Short Symbols and Untrimmed Aliases

**Symptom:** `GET /api/v1/sentiment/A` returns articles about anything containing the English article "a". `/sentiment/S` returns every article mentioning "U.S." or "S&P". `/sentiment/AI` returns the entire artificial-intelligence news cycle rather than C3.ai. The responses are well-formed and the sentiment scores are correct — they are simply about the wrong companies.

**How it surfaced:** while measuring cross-source duplication after adding BBC and SEC feeds (ADR 036), the single candidate duplicate pair turned out to be two unrelated articles matched to each other because both carried ticker `A` — one from "**A** colleague", the other from "**A**I".

**Scope, measured on the production corpus (58,426 articles):**

| | |
|---|---|
| Articles carrying at least one ticker | 34,058 |
| Attachments from 1-2 character symbols | 29.4 % of all attachments |
| Articles whose *only* tickers are 1-2 chars | 7,451 |

Worst offenders by volume: `AI` 3,488 articles (6.0 % of the corpus), `A` 1,819, `S` 1,218, `BLSH` 896, `DOW` 663, `U` 639, `P` 624.

**Root cause — two independent defects.**

1. **The bare symbol was always registered as a keyword.** `_initialize` appended the ticker to its own alias list, so one- and two-character symbols matched ordinary English. `U.S.` yields `U` and `S`; `S&P` yields `S` and `P`; `A` matches the article; `CD` matches "CD rates". The *company-name* aliases were never the problem — "Agilent Technologies" is unambiguous.

2. **Two aliases are ordinary vocabulary.** `BLSH` (Bullish Global) ships the alias `"Bullish"` and matched every "analysts turn bullish" headline. `DOW` ships `"Dow"` and matched the index rather than Dow Inc. These are the only three such entries in the dictionary; both were found by measurement, not guessed.

**A third defect found while fixing the first two.** Withholding bare short symbols initially made 69 companies unfindable — Altria, Zoom, DuPont, Agilent, Broadridge among them. Their aliases are derived upstream by truncating "X, Inc." and therefore end in a comma: `"Agilent Technologies,"`. FlashText matches exactly, so that alias never fired on the far more common "Agilent Technologies beat expectations". 2,997 tickers had *every* alias ending in punctuation.

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

Of the 884 removed attachments, 847 were `AI`, `A`, `S`, `P`, `BLSH`, `U` or `DOW`. Spot-checked headlines that lost all tickers — "The Smartest S&P 500 ETF to Buy", "U.A.E. Asks U.S. for a Wartime Financial Lifeline", "Best CD rates today" — carry no company reference at all.

**The accepted cost.** A one- or two-character ticker mentioned *only* as a bare symbol, with the company never named, is no longer matched: `"Market Digest: MKL, AVY, FISV, GT, XEL"` loses `GT`. Measured as rare — `GT` did not reach the top fifteen removed symbols — and taken deliberately in exchange for removing the noise. `tests/test_ticker_extractor.py` asserts this loss explicitly so it stays a recorded trade rather than a regression somebody later "fixes" by reverting.

**Not yet done: the existing corpus is still wrong.** This changes extraction going forward. The 34,058 already-tagged articles keep their bad tickers until `app/scripts/backfill_tickers.py` is re-run, which is a GPU-free pass over the Silver Layer. Until then the API serves the old attributions.

**Architectural lesson.** The extractor was never wrong by its own rules — FlashText found real symbols belonging to real companies, exactly as instructed. The defect was in what it was told to look for. A dictionary assembled from an authoritative source (SEC registrants) is not automatically a good matching vocabulary: authority guarantees the symbols exist, not that they are unambiguous in prose. Any exact-match entity extractor needs its vocabulary audited against the *text it will actually see*, and the audit has to be a measurement, because at 11,119 entries nobody spots `BLSH → "Bullish"` by reading.
