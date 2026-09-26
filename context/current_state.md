# Current State

_Last updated: 2026-09-26 (Stage 0 SCORED on leaderboard)_

## Overall status: STAGE 1 BLOCKING DONE (recall 0.52→0.956, gate passed) — building the scorer next
⛔ New rule: next submission must clear **local val F_0.5 ≥ 0.95** (aim 0.96 for
margin) before we spend it. Leaderboard #1 is 0.990556; rank 2005; goal is the
top. We climb one lever at a time (blocking → matcher → consistency) and
re-measure on the holdout. Blocking recall gate (≥0.95) is now PASSED; next
lever is the matcher (F_0.5). See `plan/IMPLEMENTATION_PLAN.md` §5 and
`context/next_steps.md`.

## Best leaderboard score: 0.623274 (1 submission used) · best LOCAL val F_0.5 = 0.641
| Sub # | Date | Approach | Val F_0.5 | LB F_0.5 | Notes |
|-------|------|----------|-----------|----------|-------|
| 1 | 2026-09-26 | Stage 0: within-country exact core-name block + address-Jaccard gate (tau=0.3) | 0.641 | **0.623274** | SCORED. local↔LB gap only ~0.018 → validation is trustworthy |

## KEY: validation harness confirmed reliable
Local 50k-holdout val (0.641) tracks the leaderboard (0.623) within ~0.018.
→ Tune offline with `stage0.py val` and trust it before spending submissions.
Likely-source of the small gap: test set includes France (absent from our
train-based holdout), which may be slightly harder.

## Version control (rollback safety)
- Git repo initialized at `student_resource/`; remote `origin` =
  https://github.com/YashDave11/AmazonMl.git, branch `main`.
- `dataset/` and `output/` are git-ignored (large / reproducible).
- Tagged good states are the rollback map — see `context/progress_tracker.md`.
  Current good state: tag **`v0-stage0`** (LB 0.623274). Roll back with
  `git checkout v0-stage0`.
- Workflow: before risky work, ensure last good state is committed & tagged;
  after a scoring change, add a row to `progress_tracker.md`, commit, and tag.

## Stage 0 results (validated on 50k train holdout)
- Blocking macro-recall = 0.522, mean candidates/S1 = 30.6 (cap=300).
- F_0.5 vs tau: peaks at **tau=0.30 → 0.641** (0.20→0.638, 0.40→0.622). Stable at 20k & 50k.
- Full test run: 1,732,544 S1 rows; 82.0% got ≥1 match; 312,404 empty.
- Output validated: `PASS` (utils/validate_submission.py). Files in `output/`.

## Stage 1 BLOCKING — recall gate PASSED (in progress: scorer next)
- **Diagnostic (stage1.py diag, 5k sample) reachable-recall ceilings:**
  exact-core 0.50 · name-token 0.858 · **address-token 0.957** · numeric-addr
  0.752 · **name∪address 1.000** · cross-script share 14.0%. Decisive: the
  blocker must key on address tokens, not names alone; char n-gram cosine
  plateaued at 0.74 because it ignored address and truncated top-k.
- **Blocker = word-level (1,2)-gram TF-IDF over `clean(name)+" "+clean(addr)`**,
  IDF-weighted, high-DF pruned (df>0.30N zeroed), per-country, chunked top-k
  cosine, UNIONed with the exact core-name block. (`stage1.py`, `selfcheck` OK.)
- **Blocking recall (15k holdout, K=40): 0.9558, mean 76.9 candidates/S1** —
  clears the ≥0.95 advance gate. Stable vs 3k (0.958). exact-core sanity 0.531.
  Recall by K: 10→0.924, 20→0.944, 40→0.956.
- ⚠️ **Known scaling issue:** the top-k sparse matmul is slow — 15k queries took
  ~25 min (US 621s + India 859s). Full test is 1.73M S1 → needs a speedup
  (sparse_dot_topn / feature trim / better batching) BEFORE the test-set run.
  Does NOT block development; only the final `run`. Tune candidate cap down too
  (77/S1 is fine for recall; smaller sets rank higher — revisit after scorer).

## What exists on disk (code)
- `code/business_entity_resolution/src/normalize.py` — normalization (unidecode translit,
  suffix strip, addr abbrev). Self-check passes.
- `.../src/metric.py` — exact F_0.5 (matches spec example 0.714). Self-check passes.
- `.../src/stage0.py` — blocking+matching, `val` and `run` modes. Memory-safe streaming.
- `.../src/stage1.py` — Stage 1 blocking (`selfcheck`/`val`/`diag`). Recall gate passed.
- `.../requirements.txt` (pinned), `.../README.md` (reproduce steps).
- `output/matching_results.tsv` (81MB), `output/candidate_pairs.tsv` (588MB).
- Deps installed: rapidfuzz, python-Levenshtein, Unidecode.

## What is DONE
- Read both spec PDFs (guideml.pdf, final_sumbission.pdf) fully.
- Inspected all 7 data files: row counts, columns, sample rows (see project_context.md).
- Measured GT distribution (5.6% singletons, mean 3.46 matches) and test country mix.
- Profiled environment (16.8GB RAM, 12 CPU, 4GB GPU; libs present/missing).
- Confirmed the metric, output format, and validation flow.
- **Full EDA done → `context/dataset_analysis.md`** (per-source profiling + 50k-S1
  ground-truth cross-source study). Key results: country agreement 100%;
  exact-name blocking ceiling 43.7%; char-trigram ceiling 91.8%; ~14% matches
  cross-script (Devanagari/accented); 19.1% of S1 share a core name; address
  Jaccard median 0.64. Plan revised accordingly.

## What is NOT done (the climb to ≥0.95)
- ⛔ **Upload gate now in force**: do NOT submit until local val F_0.5 ≥ 0.95
  (aim 0.96 for margin — local ran ~0.018 optimistic vs LB). Stage 0 is banked.
- Stage 1 blocking ✓ (recall 0.956). **Scorer NOT done**: next is the IDF
  composite scorer (Stage 1b) to turn candidates → matches and measure F_0.5.
- Stage 2 not started: LightGBM pair classifier on hard negatives.
- Stage 3 not started: cross-source consistency + per-entity selection +
  calibration (the milestone that should clear 0.95).
- Full-test `run` mode for Stage 1 not built yet (needs the matmul speedup).
- See `context/next_steps.md` for the exact ordered steps.

## Open decisions / risks
- 16GB RAM vs 10M+ S2/S3 records → must chunk per-country/per-source; verify
  memory before scaling any step to the full test set.
- France unseen in training → keep pipeline country-agnostic; validate a
  France-like held-out slice if possible (there is none in train, so rely on
  script/accent-robust normalization + similarity features, not country identity).
- Confirm local val F_0.5 tracks the leaderboard before spending submissions.
