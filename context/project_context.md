# Project Context — Business Entity Resolution (Amazon ML Challenge)

_Last updated: 2026-09-26_

## The task
Given business records from 3 independent, noisy sources, decide which S2/S3
records refer to the same real-world business as each **Source 1** entity.
Source 1 is the deduplicated reference. For every S1 entity we output the list
of matching S2/S3 `entity_id`s (0, 1, or many). No shared keys exist across
sources — matching is on `business_name` + `business_address` + `country`.

## Data (measured, not assumed)
| File | Rows | Notes |
|------|------|-------|
| train_source1 | 2,206,821 | reference entities |
| train_source2 | 5,034,616 | |
| train_source3 | 5,285,603 | |
| train_ground_truth | 2,206,821 | one row per S1 (incl. empties) |
| test_source1 | 1,732,544 | **must produce a row for each** |
| test_source2 | 4,887,273 | |
| test_source3 | 5,082,316 | |

Columns (all source files): `entity_id, business_name, business_address, country`.
Ground truth: `source1_entity_id, matched_entity_ids` (comma-joined S2/S3 IDs).

### Ground-truth distribution (train) — shapes our strategy
- Singletons (0 matches): **5.6%** (123,247). Predict empty → free 1.0 each.
- Mean matches per S1: **3.46**. Modal count 2–5. Max seen 11.
- Matches split roughly evenly S2 (3.69M) vs S3 (3.94M).

### Test country mix (test_source1)
India 809,986 · US 663,106 · **France 259,452** (France is unseen in training).

## Noise to handle
- Names: legal-suffix variants (Corp/Corporation, Pvt/Private, Ltd/Limited),
  `&` vs `and`, punctuation, word-order swaps, typos, DBA/trade names,
  transliteration (Devanagari for India, accents for France).
- Addresses: abbreviations (Rd/Road, St/Street), missing PIN/state, landmark
  refs ("Near SBI ATM"), reordered components, transliteration.

## Metric — F_0.5, macro-averaged per S1 entity
`F_0.5 = 1.25·P·R / (0.25·P + R)` per entity, then averaged over ALL test S1
(singletons included). Precision-heavy: a wrong ID hurts ~2× a missed one.
Singleton scores 1.0 if predicted empty, 0.0 if we predict anything.
**Implication: threshold high, prefer precision, and get singletons right.**

## Deliverables
- Leaderboard (during challenge): upload `output/matching_results.tsv` only.
- Candidate set `output/candidate_pairs.tsv`: the exact set fed to the matcher;
  smaller-per-S1 is rewarded in final ranking. Final matches ⊆ candidates.
- Final zip: `output/` (both TSVs) + `code/business_entity_resolution/`
  (`src/`, `README.md`, pinned `requirements.txt`) + filled
  `Documentation_template.md`.

## Constraints / rules
- **No external data/APIs/lookups.** Provided data only (enforced by code review).
- Final model MIT/Apache-2.0, ≤8B params. (GBM/TF-IDF are fine.)
- Country is an open set — never hard-code {US, India}.
- 5 submissions/day.

## Environment (this machine)
- Windows 11, bash shell, 12 CPUs, **16.8 GB RAM** (the binding constraint),
  RTX 3050 Laptop **4 GB VRAM** (too small for large-model embedding at scale).
- Installed: numpy, pandas, scipy, scikit-learn, xgboost, lightgbm.
- **Missing (install when needed):** rapidfuzz, python-Levenshtein, unidecode,
  faiss, sentence-transformers, torch. All optional libs must stay MIT/Apache.
- Plan for out-of-core / per-country / per-source chunking — 10M+ S2/S3 records
  cannot all sit in RAM alongside feature matrices.

## Key paths
- Working dir: `student_resource/`
- Data: `dataset/train/`, `dataset/test/`
- Validator: `utils/validate_submission.py` (stdlib only; `--check-ids` optional)
- Our code will live in: `code/business_entity_resolution/src/`
- Outputs: `output/`
