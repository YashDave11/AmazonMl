# Progress Tracker

Chronological log of every meaningful change, its score, and the git ref to
roll back to. **Append a row here whenever a submission is made or a stage
lands.** Pair with `current_state.md` (current snapshot) — this file is the
timeline + rollback map.

## Targets
- [x] Milestone 1 — clear **0.5** on leaderboard. (0.623274 ✓)
- [ ] Milestone 2 — reach **~0.7** (Stage 1: fuzzy blocking + IDF scoring).
- [ ] Milestone 3 — reach **0.8–0.9** (Stage 2: LightGBM pair classifier).

## Score log
| # | Date (UTC) | Stage / change | Val F_0.5 | LB F_0.5 | Git ref | Rollback |
|---|-----------|----------------|-----------|----------|---------|----------|
| 1 | 2026-09-26 | Stage 0: within-country exact core-name block + address-Jaccard gate (tau=0.3) | 0.641 | **0.623274** | `v0-stage0` | `git checkout v0-stage0` |

_Best leaderboard so far: **0.623274** (Stage 0). Submissions used today: 1/5._

## How to use this tracker
- **Before a risky change:** ensure the last good state is committed & tagged
  (see the "Git ref" column). Then experiment freely.
- **After a change that scores:** add a row with val + LB score and the commit
  hash/tag. Tag good states: `git tag -a vN-desc -m "LB=0.xxx" && git push --tags`.
- **To roll back** to a known-good state: `git checkout <ref>` (or
  `git reset --hard <ref>` to discard, only when you're sure).
- Outputs (`output/`) and `dataset/` are git-ignored (too large / provided
  data). Reproduce outputs from code via `stage0.py run`; they are NOT versioned.

## Change history (detail)
### 2026-09-26 — Stage 0 (ref `v0-stage0`)
- Built `normalize.py`, `metric.py`, `stage0.py`; validated F_0.5 harness.
- Blocking recall 0.522, mean 30.6 candidates/S1; tau=0.30 optimal.
- LB 0.623274. Local↔LB gap ~0.018 → validation trusted.
- Next: Stage 1 fuzzy blocking to lift the 0.52 recall ceiling.
