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

## STEP 1 ✓ DONE — Stage 1 blocking: recall 0.52 → 0.956 (gate passed)
Diagnostic (`stage1.py diag`) proved name∪address token blocking has a 1.00
recall ceiling (address alone 0.957); char n-gram cosine plateaued at 0.74.
Blocker = word (1,2)-gram TF-IDF over `clean(name)+clean(addr)`, IDF-weighted,
high-DF pruned, per-country, top-k cosine ∪ exact core-name. 15k holdout, K=40:
**recall 0.9558, 76.9 cand/S1**. ⚠️ matmul is slow (~25min/15k) — needs a
speedup before the full 1.73M `run`; does not block scorer development.

## STEP 2 (now) — Stage 1b scorer: candidates → matches, measure F_0.5
Turn the blocking candidates into predicted matches and get the first Stage 1
F_0.5 on the holdout (expected 0.75–0.85; NOT yet uploadable):
1. Per (S1, candidate) composite score from features we can compute cheaply:
   rapidfuzz token_sort/token_set on name, IDF-weighted token overlap on name and
   on address, shared numeric (street/PIN) tokens, cosine already have.
   Down-weight legal/generic tokens (already dropped in name_core; keep IDF).
2. Precision-first threshold tuned on the F_0.5 curve (favour empty when weak —
   protects the 5.6% singletons worth 1.0 each).
3. Report F_0.5 + precision/recall on the holdout. This replaces Stage 0's raw
   address-Jaccard gate. Interim — the LightGBM model (Stage 2) supersedes it.

## STEP 3 — Stage 2: LightGBM pair classifier (expected local 0.88–0.94)
Positives = GT matches; hard negatives = blocking candidates not in GT. Features
= name/address similarity family + `country_match` (boolean, generalizes to
France) + source flag. Tune probability threshold for F_0.5 (expect high cut).
Calibrate on holdout. Still below the gate — do not upload yet.

## STEP 4 — Stage 3: consistency + per-entity selection + calibration (≥0.95 → UPLOAD)
- Per-S1 selection (abs prob cut + relative margin off top candidate; prefer
  empty when best is weak — protects the 5.6% singletons worth 1.0 each).
- Cross-source consistency: also block/score S2↔S3; a consistent triangle
  (S1–S2, S1–S3, S2–S3) is high-confidence; demote inconsistent lone edges.
- Per-country/per-source threshold tuning + probability calibration.
- **When local F_0.5 ≥ 0.95 (aim 0.96): run validator, then UPLOAD.**

## STEP 5 — Stage 4: residual error-mining toward 0.99 (after banking ≥0.95)
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
