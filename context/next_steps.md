# Next Steps

_Last updated: 2026-09-26 (Stage 0 done)_

## RIGHT NOW — upload submission #1 (user action)
`output/matching_results.tsv` is generated and passes the validator (local val
F_0.5 ≈ 0.641). Upload it to the Unstop portal. Then record the leaderboard
score in `context/current_state.md` and confirm local-vs-leaderboard
correlation before iterating (if they diverge badly, fix validation first).

To regenerate: `cd code/business_entity_resolution/src && python stage0.py run --tau 0.3`

## Then — Milestone 2 (Stage 1): fuzzy blocking + better scoring (target ~0.7)
Current ceiling is blocking recall 0.52 (exact core-name only). Lift it:

1. **Char n-gram (3–4) TF-IDF blocking within country** over transliterated
   `name_norm` (sklearn `TfidfVectorizer` + sparse cosine top-k). This is the
   recall backbone (EDA: 91.8% of matches share a name trigram). Union with the
   existing exact-core block and an **address n-gram/number block** for the
   ~8% cross-script tail. Measure combined recall vs mean candidates/S1; cap
   candidates per S1 to keep the set small (scored in final ranking).
2. **Verify the unidecode Devanagari lift** empirically (EDA open question):
   does translit raise ASCII↔Devanagari name similarity enough to block, or must
   those ride the address block? Decide from measurement.
3. **IDF-weighted scoring**: replace raw address Jaccard with a composite
   (rapidfuzz token_sort/token_set on name + IDF-weighted token overlap on name
   & address). Down-weight legal/generic tokens (limited/private/services/...).
   Re-tune the accept threshold on the F_0.5 curve.
4. Keep candidate size small — it's rewarded in final ranking.

## Then — Milestone 3 (Stage 2): LightGBM pair classifier (target 0.8→0.9)
Positives = GT matches; hard negatives = blocking candidates not in GT. Features
= name/address similarity family + `country_match` (boolean, generalizes to
France) + source flag. Tune probability threshold for F_0.5 (expect high cut).

## Guardrails (unchanged)
- Prototype on a sample; watch RAM (peaked fine in Stage 0). Chunk per source.
- Precision > recall on every threshold call (F_0.5).
- Re-run the validator before EVERY upload. 5 subs/day.
- Deps rapidfuzz / python-Levenshtein / Unidecode already installed & approved.
