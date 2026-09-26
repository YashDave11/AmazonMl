# Amazon ML Challenge — Business Entity Resolution

## READ FIRST — every session, before any other action
Before doing ANYTHING else in this project, read these files in order:
1. `context/project_context.md` — the challenge, data, metric, constraints, environment
2. `context/dataset_analysis.md` — measured facts about the data + design implications
3. `context/current_state.md`   — what exists on disk, current best score, what's done
4. `context/next_steps.md`      — the exact next action to take right now

Then read `plan/IMPLEMENTATION_PLAN.md` for the full staged strategy.

After finishing any unit of work, UPDATE `context/current_state.md` and
`context/next_steps.md` (and `context/dataset_analysis.md` if you learn something
new about the data) so the next session resumes cleanly. This is mandatory.

## Hard rules (violating any = disqualification or rejected submission)
- NO external data, APIs, geocoding, or entity lookups. Provided data ONLY.
- Output is TSV with exact headers; EVERY test S1 entity gets exactly one row
  (empty `matched_entity_ids` = "no match", which is a correct, scored answer).
- No duplicate S1 rows; no duplicate IDs within a list; only S2-/S3- IDs.
- Final model must be MIT/Apache-2.0 licensed and ≤8B parameters.
- Do NOT hard-code countries. France appears only in test — pipeline must be
  country-agnostic.

## The one number we optimise
F_0.5 (precision weighted 2× over recall), macro-averaged per S1 entity.
When in doubt, favour PRECISION: a false merge costs more than a missed match.
Correctly leaving a singleton empty is worth a full 1.0 on that entity.

## Validate before every leaderboard upload
`python utils/validate_submission.py -m output/matching_results.tsv -c output/candidate_pairs.tsv -t dataset/test`
Only `matching_results.tsv` is scored; `candidate_pairs.tsv` is reviewed for
blocking quality (smaller candidate set per S1 = higher final ranking).
Budget: 5 submissions/day.
