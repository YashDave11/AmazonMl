# Business Entity Resolution — Pipeline

Resolves which Source-2/3 records match each Source-1 business entity.
F_0.5-optimised (precision-weighted). See `../../context/` for the full
methodology and data analysis.

## Setup
```bash
pip install -r requirements.txt
```

## Reproduce end-to-end

All commands run from `src/`. Paths default to the repo's `dataset/` and
`output/` folders (`../../../` relative to `src/`).

### 1. Sanity-check the building blocks
```bash
python normalize.py    # normalization self-check
python metric.py       # F_0.5 self-check (matches the spec example, 0.714)
```

### 2. Tune / validate on a training holdout (prints macro F_0.5 vs tau)
```bash
python stage0.py val --sample 50000
```
Reports blocking recall, mean candidates/S1, and the F_0.5 curve over the
address-Jaccard threshold `tau`. Current best: **tau=0.30 → F_0.5 ≈ 0.641**
(blocking recall ceiling ≈ 0.52).

### 3. Generate the submission on the test set
```bash
python stage0.py run --tau 0.3
```
Writes `output/matching_results.tsv` (leaderboard file) and
`output/candidate_pairs.tsv` (blocking set fed to the matcher).

### 4. Validate output format before uploading
```bash
cd ../../..            # student_resource/
python utils/validate_submission.py \
    -m output/matching_results.tsv -c output/candidate_pairs.tsv -t dataset/test
```

## Method (Stage 0 baseline)
- **Normalize** (`normalize.py`): unidecode transliteration + accent-fold,
  lowercase, punctuation strip, `&`→`and`, legal-suffix removal, address
  abbreviation canonicalization.
- **Block** (`stage0.py`): within-country exact match on the sorted,
  suffix-stripped `name_core`. Streaming, memory-bounded (only S2/S3 records
  sharing an S1 core name are indexed; buckets capped).
- **Match** (`stage0.py`): keep a candidate when address token Jaccard ≥ `tau`.
  The address gate defends precision against same-name/different-business S1
  collisions (~19% of S1 share a core name — see data analysis).

## Files
- `normalize.py` — text normalization (shared by all stages).
- `metric.py` — exact challenge F_0.5 (per-entity, macro-averaged).
- `stage0.py` — blocking + matching + validation/run entry points.

Later stages (fuzzy TF-IDF blocking, LightGBM pair classifier) build on these;
see `../../context/next_steps.md` and `../../plan/IMPLEMENTATION_PLAN.md`.
