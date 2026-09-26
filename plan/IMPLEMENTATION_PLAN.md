# Implementation Plan — Business Entity Resolution

_Amazon ML Challenge · 72-hour hackathon · last updated 2026-09-26_

This is the full strategy. Operational state lives in `context/`; read those
first. This document is the "why" and the staged "how".

> **Revised 2026-09-26 after full EDA** (see `context/dataset_analysis.md`).
> The data measurements below are load-bearing — the strategy changed because of
> them (country is a hard partition; exact-name blocking only reaches 43.7%;
> transliteration is mandatory; address is mandatory to disambiguate 19% of
> same-name S1 entities).

---

## 1. Problem in one paragraph

For each of 1.73M **Source-1** test entities, return the S2/S3 records that are
the same real-world business (0–many each), using only `business_name`,
`business_address`, `country`. Scored by **macro F_0.5** (precision weighted 2×).
No external data. We also submit the blocking candidate set, and smaller
candidate sets per S1 are rewarded in final ranking.

## 2. What the metric tells us to do

- **Precision first.** F_0.5 punishes a false merge ~2× a miss. Every threshold
  and tie-break should lean toward "don't merge unless confident."
- **Singletons are free points.** 5.6% of entities have no match; predicting
  empty scores 1.0. Never invent matches for a weak-signal entity — an empty
  row beats a wrong guess.
- **Per-entity averaging** means one S1 with 5 true matches is worth the same as
  one singleton. Getting the *common* 2–5 match entities right is where the mass
  of the score is (mean 3.46 matches).
- Recall still matters (it's in the numerator) — but recall bought with
  precision loss is usually a bad trade here. Tune the threshold on the F_0.5
  curve, not on recall.

## 3. Two-stage architecture (blocking → matching)

Brute force is 1.7M × 10M ≈ 1.7×10¹³ pairs — impossible. Every serious ER
system is **blocking → pairwise matching**, and the challenge scores both.

```
S1, S2, S3 test  ──normalize──>  keys
                                   │
                        ┌──────────┴───────────┐
                        │   BLOCKING (recall)  │  cut 10M → tens of candidates / S1
                        └──────────┬───────────┘
                                   │  candidate_pairs.tsv  (submitted, reviewed)
                        ┌──────────┴───────────┐
                        │  MATCHING (precision)│  score each candidate, threshold
                        └──────────┬───────────┘
                                   │  matching_results.tsv  (leaderboard-scored)
```

- **Blocking** sets the recall ceiling: a true match not in candidates can never
  be recovered. So blocking must be high-recall — but also *small* (scored). We
  balance with a union of cheap keys + a per-S1 cap. **All blocking runs strictly
  within a country** (EDA: 100% of true matches share country) — this alone cuts
  the search space ~3× and can never cost recall.
- **Matching** sets precision: score each (S1, candidate) pair and keep only
  confident ones. This is where F_0.5 is won.

## 4. Normalization (shared foundation for everything)

Both blocking and matching depend on good text normalization. One module,
country-agnostic (do NOT branch on {US, India}):

- **Transliteration is mandatory, not cosmetic** (EDA finding #4): ~14% of true
  matches pair a Latin S1 with a Devanagari (4%) or accented (10%) S2/S3 record,
  and Devanagari name-Jaccard is ~0.02 raw. Run `unidecode` (Devanagari→Latin
  phonetic) + NFKD accent-folding so cross-script partners canonicalise into the
  same blocks/features. **Validate the Devanagari lift empirically** — phonetic
  romanisation may not exactly match S1's romanisation; where it fails, those
  matches must fall back to address-based blocking.
- Lowercase; unicode-normalize; strip punctuation; `&`→`and`; collapse whitespace.
- Expand the abbreviation map seen in the data:
  `corp→corporation, pvt→private, ltd→limited, co→company, inc, llp, llc, sarl,
  sas` (sarl/sas are French — test-only), `rd→road, st→street, ave→avenue,
  blvd→boulevard, ste/suite, apt`, etc.
- Produce several fields per record:
  - `name_norm` (full, transliterated) and `name_core` (minus legal suffixes)
  - `name_tokens` (set) with legal/generic tokens flagged for IDF down-weighting
    (`limited/private/llc/services/center/...` are near-stopwords per EDA)
  - `addr_norm`, `addr_tokens`, extracted `numbers` (street/PIN — PIN present in
    only ~5%, so use all address tokens, not just PIN), best-effort
    `city`/`region` (trailing comma components; addresses are comma-structured).
- Everything token-based so word-order swaps don't matter.

Self-check: assert `Corp`≡`Corporation`, `Pvt Ltd`≡`Private Limited`,
`A & B`≡`A and B`, and a known Devanagari↔Latin match pair canonicalise close.

## 5. Staged plan (the submission ladder)

We have 5 subs/day. Each stage is independently shippable; ship the simplest
thing that scores, measure, then climb. **Never skip local F_0.5 validation.**

> ### ⛔ SUBMISSION GATE (revised 2026-09-26, updated target)
> **Do NOT upload to the leaderboard until local val F_0.5 ≥ 0.95.** The field
> is tight — leaderboard #1 is **0.990556**, our rank is 2005, and Stage 0
> (LB 0.623274) is already banked and safe. Intermediate stages are developed
> and tuned **entirely on the local holdout**; we spend a submission only when
> we can clear 0.95. Because local ran ~0.018 optimistic vs. LB at Stage 0 (and
> France is unseen in our holdout), **aim for local ≥ 0.96 to leave margin.**
> After we bank ≥0.95, keep climbing toward 0.99 (the real goal is the top).
>
> The stages below are unchanged in *approach*; only the target bands moved up.
> We climb ONE lever at a time and re-measure — blocking recall first (it caps
> everything), then the matcher, then consistency/calibration.

### Target ladder (each gated by the local holdout, not the board)
| Step | Lever | Blocking recall | Expected local F_0.5 |
|------|-------|-----------------|----------------------|
| Stage 0 ✓ | exact core-name + addr gate | 0.52 | 0.641 (LB 0.623) |
| Stage 1 | fuzzy union blocking + composite scoring | ~0.95+ | 0.75–0.85 |
| Stage 2 | LightGBM pair classifier | (same) | 0.88–0.94 |
| Stage 3 | cross-source consistency + per-entity selection + calibration | — | **0.95+ → UPLOAD** |
| Stage 4 | residual error-mining toward the top | — | 0.96 → 0.99 |

### Stage 0 — deterministic baseline ✓ DONE (LB 0.623274)
Highest-precision thing that exists:
- Partition by country (hard). Blocking: candidates = S2/S3 records with the
  **same `name_core` within the same country**, gated by ≥1 shared address token.
- Match rule: accept if `name_norm` exact-equal AND address token Jaccard ≥ τ
  (τ=0.30 optimal). Recall capped ~0.52 by design — the floor we banked.

### Stage 1 — fuzzy blocking + composite scoring (local target 0.75–0.85)
**This is the recall unlock — the single biggest lever (0.52 → ~0.95+).**
- Blocking recall engine (all within country): char n-gram (3–4) **TF-IDF** over
  transliterated `name_norm` — the backbone (EDA: 91.8% of matches share a name
  trigram). Take top-k nearest S2/S3 per S1 by sparse cosine. **Union** with:
  content-token block (84.8% ceiling) and an **address n-gram/number block** to
  reach the ~8% (esp. cross-script) where the name is useless but the address
  overlaps. Measure combined recall vs. mean candidates/S1 and pick the knee.
  **Gate to advance: blocking recall ≥ 0.95 on the holdout.**
- Verify the unidecode Devanagari lift here: if translit doesn't lift
  ASCII↔Devanagari name similarity enough, those matches must ride the address block.
- Scoring: rule-based composite from name sim (rapidfuzz token_sort + char-cosine,
  IDF-weighted so legal/generic tokens don't dominate), address sim, shared
  numbers/city. Threshold for F_0.5. (Interim — replaced by the model in Stage 2.)

### Stage 2 — supervised pair classifier (local target 0.88–0.94)
- Training pairs: positives = GT matches; negatives = blocking candidates that
  are NOT in GT (hard negatives, the ones that actually confuse the matcher).
  Balance/subsample negatives (they vastly outnumber positives).
- Features per (S1, candidate) pair:
  - Name: token Jaccard, char-ngram cosine, rapidfuzz ratio/token_sort/
    token_set, Levenshtein ratio, length ratio, shared-rare-token count (IDF),
    prefix/acronym match, digit-set overlap.
  - Address: same similarity family on `addr_norm`/`addr_tokens`, shared
    number tokens (street/PIN), shared city/region token, both-empty flag.
  - Meta: `country_match` (boolean, generalizes to France — do NOT one-hot the
    country value), name-contains, source (S2 vs S3) as a feature.
- Model: **LightGBM** (fast, CPU-friendly, MIT/Apache, strong on tabular)
  predicting P(match). Threshold tuned on the F_0.5 curve (precision-heavy →
  high cut). Calibrate on the holdout.

### Stage 3 — consistency + per-entity selection + calibration (local target 0.95+ → FIRST HIGH UPLOAD)
The lever that turns a good classifier into a great macro-F_0.5:
- **Per-S1 match selection, not a global threshold.** Matches are many-to-one;
  select per entity — e.g. absolute prob cut + a relative margin off the top
  candidate, and prefer emitting empty when the best is weak (protects the 5.6%
  singletons, each worth 1.0).
- **Cross-source consistency (the out-of-the-box edge).** 80% of S1 match BOTH a
  S2 and a S3 record. Also block S2↔S3 and score them; a consistent triangle
  (S1–S2, S1–S3, S2–S3 all similar) is high-confidence → raise recall without
  hurting precision; an inconsistent lone edge → demote. This exploits structure
  a generic pairwise matcher ignores.
- Per-country / per-source threshold tuning; probability calibration.
- **Gate: local F_0.5 ≥ 0.95 (aim 0.96 for margin) → then upload.**

### Stage 4 — residual error-mining toward the top (0.96 → 0.99)
- Error analysis on holdout false-merges vs. misses; fix the dominant bucket
  each iteration (cross-script names, landmark/PIN-sparse Indian addresses,
  abbreviation edge cases, France accents).
- Squeeze blocking recall toward ~0.99 without inflating candidate size (scored).
- Consider a small MIT/Apache text-embedding model for the hard residual names
  IF CPU-feasible at scale (4 GB GPU limits this) — only if hand features plateau.
- Small ensembles / feature additions only when they pay on the holdout.

## 6. Local validation harness (build in Stage 0, reuse forever)

- Hold out ~30k train S1 entities (+ their GT rows) as a validation set,
  disjoint from anything used to fit thresholds/model.
- Implement the **exact** metric: per-entity P/R → F_0.5, singleton = 1.0 iff
  predicted empty, macro-average over the held-out S1. This number is the only
  thing we trust before spending a submission.
- Also report blocking recall (fraction of GT matches present in candidates)
  and mean candidates/S1 (the reduction ratio the organizers score).
- Sanity: confirm local F_0.5 moves the same direction as the leaderboard after
  the first real submission; if they diverge, fix validation before iterating.

## 7. Engineering constraints (16.8 GB RAM is the boss)

- ~10M S2/S3 + 1.7M S1 records. Do not hold all text + feature matrices at once.
- Stream and process **per country, per source**; int-code entity IDs and keys;
  use categorical/`category` dtypes; keep TF-IDF sparse; free intermediates.
- Prototype every step on a **50k-S1 sample** before touching the full test set.
- Kill any step that exceeds ~12 GB and redesign it (chunk harder / go on-disk).
- Parallelize the embarrassingly-parallel parts across the 12 CPUs; the 4 GB GPU
  is not relied upon (torch/faiss not installed) — CPU LightGBM + sparse
  sklearn is the default path.

## 8. Deliverables checklist (for the final zip)

- `output/matching_results.tsv` + `output/candidate_pairs.tsv` (final ⊆ candidates).
- `code/business_entity_resolution/src/` — runnable pipeline, `README.md`
  (data→blocking→matching→output), pinned `requirements.txt`.
- Filled `Documentation_template.md`: methodology, blocking strategy, model +
  features, and the precision/recall reasoning above.
- All libs MIT/Apache; no external data anywhere in the code path.

## 9. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| OOM on full test | per-country/source chunking; sample-first; monitor RSS |
| Blocking drops true matches | measure recall on val; union of complementary keys |
| Over-merging tanks precision | high threshold; require name+address agreement |
| France (unseen) underperforms | country-agnostic features; `country_match` boolean only |
| Local val ≠ leaderboard | verify correlation after sub #1 before iterating |
| Wasting daily submissions | always run validator; only submit when val improves |

## 10. Definition of done per milestone
- M1 (Stage 0): validator PASS, val F_0.5 ≥ 0.5, first leaderboard score logged. ✓ (0.623)
- M2 (Stage 1): blocking recall ≥ 0.95 on holdout; interim val F_0.5 0.75–0.85. Dev only.
- M3 (Stage 2): val F_0.5 0.88–0.94 with LightGBM, threshold tuned for F_0.5. Dev only.
- M4 (Stage 3): **val F_0.5 ≥ 0.95 (aim 0.96) → validator PASS → FIRST HIGH UPLOAD.**
- M5 (Stage 4): climb toward 0.99; final zip + methodology doc assembled.
