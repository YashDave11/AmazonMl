# Next Steps

_Last updated: 2026-09-26 (Stage 0 scored; new ≥0.95 upload gate in force)_

## ⛔ THE GATE — do not upload until local val F_0.5 ≥ 0.95 (aim 0.96 for margin)
Stage 0 (LB 0.623274) is banked and safe. We now develop and tune the next
stages **entirely on the 50k local holdout** and spend a submission ONLY when
local clears 0.95. Local ran ~0.018 optimistic vs LB at Stage 0 (France is
unseen in our holdout), so target local ≥0.96 before uploading. Leaderboard #1
is 0.990556 — after banking ≥0.95 we keep climbing toward the top.

We climb ONE lever at a time and re-measure. Order is fixed: blocking recall
first (it caps everything), then the matcher, then consistency/calibration.

## STEP 1 (now) — Stage 1: fuzzy union blocking, lift recall 0.52 → ≥0.95
The current 0.52 blocking recall is the hard ceiling on everything. Lift it:

1. **Char n-gram (3–4) TF-IDF blocking within country** over transliterated
   `name_norm` (sklearn `TfidfVectorizer` + sparse cosine top-k). This is the
   recall backbone (EDA: 91.8% of matches share a name trigram). Union with the
   existing exact-core block and an **address n-gram/number block** for the
   ~8% cross-script tail. Measure combined recall vs mean candidates/S1; cap
   candidates per S1 to keep the set small (scored in final ranking).
   **Advance gate: blocking recall ≥ 0.95 on the holdout.**
2. **Verify the unidecode Devanagari lift** empirically: does translit raise
   ASCII↔Devanagari name similarity enough to block, or must those ride the
   address block? Decide from measurement.
3. **IDF-weighted composite scoring** (interim matcher): rapidfuzz
   token_sort/token_set on name + IDF-weighted token overlap on name & address,
   down-weighting legal/generic tokens (limited/private/services/...). Re-tune
   the accept threshold on the F_0.5 curve. Expected local 0.75–0.85 — NOT yet
   uploadable; this feeds Stage 2.

## STEP 2 — Stage 2: LightGBM pair classifier (expected local 0.88–0.94)
Positives = GT matches; hard negatives = blocking candidates not in GT. Features
= name/address similarity family + `country_match` (boolean, generalizes to
France) + source flag. Tune probability threshold for F_0.5 (expect high cut).
Calibrate on holdout. Still below the gate — do not upload yet.

## STEP 3 — Stage 3: consistency + per-entity selection + calibration (≥0.95 → UPLOAD)
- Per-S1 selection (abs prob cut + relative margin off top candidate; prefer
  empty when best is weak — protects the 5.6% singletons worth 1.0 each).
- Cross-source consistency: also block/score S2↔S3; a consistent triangle
  (S1–S2, S1–S3, S2–S3) is high-confidence; demote inconsistent lone edges.
- Per-country/per-source threshold tuning + probability calibration.
- **When local F_0.5 ≥ 0.95 (aim 0.96): run validator, then UPLOAD.**

## STEP 4 — Stage 4: residual error-mining toward 0.99 (after banking ≥0.95)
Error-bucket analysis on holdout false-merges vs misses; fix the dominant bucket
each iteration; squeeze blocking recall toward 0.99 without inflating candidate
size; consider a small MIT/Apache text embedding for hard residual names only if
CPU-feasible and hand features plateau.

## Guardrails (unchanged)
- Prototype on a sample; watch RAM (peaked fine in Stage 0). Chunk per source.
- Precision > recall on every threshold call (F_0.5).
- Re-run the validator before EVERY upload. 5 subs/day. Only upload at ≥0.95.
- Deps rapidfuzz / python-Levenshtein / Unidecode already installed & approved.
- Before risky work: ensure last good state is committed & tagged (rollback map
  in `progress_tracker.md`, current good tag `v0-stage0`).
