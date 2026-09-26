# Current State

_Last updated: 2026-09-26 (Stage 0 SCORED on leaderboard)_

## Overall status: STAGE 0 SUBMITTED & SCORED — on the board at 0.623, target 0.5 cleared

## Best leaderboard score: 0.623274 (1 submission used) · best LOCAL val F_0.5 = 0.641
| Sub # | Date | Approach | Val F_0.5 | LB F_0.5 | Notes |
|-------|------|----------|-----------|----------|-------|
| 1 | 2026-09-26 | Stage 0: within-country exact core-name block + address-Jaccard gate (tau=0.3) | 0.641 | **0.623274** | SCORED. local↔LB gap only ~0.018 → validation is trustworthy |

## KEY: validation harness confirmed reliable
Local 50k-holdout val (0.641) tracks the leaderboard (0.623) within ~0.018.
→ Tune offline with `stage0.py val` and trust it before spending submissions.
Likely-source of the small gap: test set includes France (absent from our
train-based holdout), which may be slightly harder.

## Stage 0 results (validated on 50k train holdout)
- Blocking macro-recall = 0.522, mean candidates/S1 = 30.6 (cap=300).
- F_0.5 vs tau: peaks at **tau=0.30 → 0.641** (0.20→0.638, 0.40→0.622). Stable at 20k & 50k.
- Full test run: 1,732,544 S1 rows; 82.0% got ≥1 match; 312,404 empty.
- Output validated: `PASS` (utils/validate_submission.py). Files in `output/`.

## What exists on disk (code)
- `code/business_entity_resolution/src/normalize.py` — normalization (unidecode translit,
  suffix strip, addr abbrev). Self-check passes.
- `.../src/metric.py` — exact F_0.5 (matches spec example 0.714). Self-check passes.
- `.../src/stage0.py` — blocking+matching, `val` and `run` modes. Memory-safe streaming.
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

## What is NOT done (everything else)
- No normalization module, no blocking, no features, no model, no submission.
- No local F_0.5 validation harness.
- Missing libs (rapidfuzz, unidecode, python-Levenshtein) not yet installed.

## Open decisions / risks
- 16GB RAM vs 10M+ S2/S3 records → must chunk per-country/per-source; verify
  memory before scaling any step to the full test set.
- France unseen in training → keep pipeline country-agnostic; validate a
  France-like held-out slice if possible (there is none in train, so rely on
  script/accent-robust normalization + similarity features, not country identity).
- Confirm local val F_0.5 tracks the leaderboard before spending submissions.
