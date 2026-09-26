# Dataset Analysis — Business Entity Resolution

_Measured 2026-09-26 from `dataset/` (full per-source profiling + a 50k-S1
ground-truth cross-source study). **Read this before any pipeline change** —
every design decision below is anchored to a number here, not a guess._

---

## TL;DR — the 7 findings that drive the design

1. **Country agreement among true matches = 100.00%.** Not one cross-country
   match in 172k analysed pairs. → Partition EVERYTHING by country. Never emit a
   cross-country match. This is a free, hard precision gate and an ~3× search-space cut.
2. **Exact (suffix-stripped) name equality recovers only 43.7% of true matches.**
   A name-equality baseline is precise but leaves >56% of recall on the table.
3. **Char-trigram overlap is the recall backbone: 91.8% of true matches share a
   name 3-gram; 84.8% share a content token.** → Blocking must be
   char-n-gram/token based, not exact. Ceiling ≈ 92% from name alone.
4. **~14% of matches are cross-script and nearly invisible to name matching.**
   S1 is always Latin; matched S2/S3 are Devanagari (4%, mean name-Jaccard **0.02**)
   or accented Latin/French (10%, mean **0.33**). → **Transliteration
   (unidecode) + accent-folding is mandatory, not polish.** The Devanagari 4% is
   unreachable by raw name comparison — recover it via transliteration and/or address.
5. **19.1% of S1 entities share a suffix-stripped "core name" with another S1.**
   S1 is deduplicated as *entities*, not as *names*. → Name alone over-merges;
   **address is mandatory to disambiguate** same-name businesses. Critical for F_0.5.
6. **Address is a strong second signal:** among true matches with both addresses
   present, address token Jaccard median 0.64. Only 4.3% of matched records have
   an empty address. → Address rescues the ~8–15% of matches with weak name overlap.
7. **80% of S1 entities match BOTH a S2 and a S3 record;** 5.6% are singletons.
   Matches are many-to-one and roughly balanced across S2/S3.

---

## Scale (exact row counts)

| File | Rows | empty name | empty addr | empty country |
|------|-----:|-----------:|-----------:|--------------:|
| train_source1 | 2,206,821 | 0% | 0% | 0 |
| train_source2 | 5,034,616 | 0% | 3.36% | 0 |
| train_source3 | 5,285,603 | 0% | 3.33% | 0 |
| train_ground_truth | 2,206,821 | — | — | — |
| test_source1 | 1,732,544 | 0% | 0% | 0 |
| test_source2 | 4,887,273 | 0% | 2.65% | 0 |
| test_source3 | 5,082,316 | 0% | 2.68% | 0 |

`business_name` and `country` are never empty. Only S2/S3 have missing
addresses (~3%). S1 never has an empty address.

## entity_id format
Prefix `S1-/S2-/S3-` + a numeric part, almost always 9 digits (~90%), tail of
8/7/6/5-digit ids. IDs look like random draws — **no sequential ordering, no
cross-source numeric correlation**. The number carries no matching signal; do
not try to exploit it.

## Country distribution
| | US | India | France |
|---|---:|---:|---:|
| train_s1 | 1,323,633 | 883,188 | — |
| test_s1 | 663,106 | 809,986 | **259,452** |
| test_s2 | 1,871,330 | 2,312,565 | 703,378 |
| test_s3 | 1,945,701 | 2,405,000 | 731,615 |

France (~15% of test S1) is **absent from training** — every country-specific
choice must generalise. India is the largest test country.

## Per-source character / language profile

- **S1 (reference):** 100% ASCII names (train). Test S1 gains 2.4% accented
  (France). No Devanagari in S1 — the reference is always romanised/Latin.
- **S2 & S3:** genuinely multilingual. Names: ~6% Devanagari, ~9–11% accented
  Latin, rest ASCII. Addresses similar. **This is the asymmetry that matters:**
  S1 is Latin but its true S2/S3 partners may be in native script.
- Addresses are comma-structured (mode 2 commas ≈ "street, city, region"); ~90%
  contain a digit; PIN/ZIP present in only ~5–7%; landmark words ("near/opp/
  behind") in 3–5% (more common in India). So structured parsing helps but
  can't rely on PIN.

## Name composition
- Median name length ~24–25 chars; legal suffixes are extremely common:
  `limited, private, ltd, pvt, llc, inc, corp, co, llp, group, holdings, sarl,
  sas` (the last two are French — appear only in test). Top name "tokens" are
  dominated by these suffixes + generic words (`services, center, partners,
  associates, care, solutions`). → suffix stripping + generic-token
  down-weighting (IDF) is essential; these tokens carry little identity signal.
- Raw duplicate names: 28–30% within S1, 12–15% within S2/S3 (lowercased exact).

## Ground-truth structure (from 50k-S1 sample, 172,488 true pairs)

- Per S1: singleton 5.5%, matches S2-only 6.5%, S3-only 7.4%, **both 80.6%**.
- **100% of matches share the S1 country.** (hard partition — see finding #1)
- Mean matches/S1 = 3.46 (from full GT); modal 2–5, max 11.

### Blocking recall ceilings (single-key, measured on true pairs)
| Blocking key | recall ceiling |
|---|---:|
| exact suffix-stripped core name | 43.70% |
| share ≥1 content token (non-suffix) | 84.82% |
| share ≥1 name char-trigram | **91.80%** |

→ A single blocker tops out ~92% on name. The remaining ~8% need **address- and
transliteration-based blocking** to be reachable at all. Design blocking as a
**union** of keys, then measure combined recall (should beat any single row).

### Similarity distributions among true matches
- **Name token Jaccard:** median 0.67, mean 0.62, p90 1.00 — but **20.8% of true
  pairs have Jaccard < 0.34** and p10 = 0.00 (no token overlap). Long tail of
  hard matches; fuzzy/char features and address are what catch them.
- **By script pair:** ASCII↔ASCII mean 0.68 (86% of pairs); ASCII↔accented mean
  0.33 (10%); **ASCII↔Devanagari mean 0.02** (4%). The cross-script pairs are
  the hard tail → transliteration is the lever (see #4).
- **Address token Jaccard** (both non-empty, ~96% of pairs): median 0.64, p10
  0.30. Strong and available almost always. Shared PIN only 5% (PINs too sparse
  to rely on; use full-address token/number overlap instead).

### Same-name-different-business hazard
19.1% of sampled S1 share a core name with another S1 entity. Two distinct
businesses can carry identical names → **matching on name without address
agreement will merge them and destroy precision.** The matcher must require
address agreement (or another strong signal) whenever a name is ambiguous.

---

## Design implications (what changes vs. a generic solution)

These are the non-obvious, data-earned moves — the edge over a generic
name-fuzzy-match pipeline:

1. **Hard country partition** (100% agreement): block and match strictly within
   country. Instant precision floor + 3× smaller search space. Generic pipelines
   often leave this soft — we make it hard.
2. **Transliteration-first normalization**: fold Devanagari (unidecode) and
   accents (NFKD) into a Latin canonical form *before* blocking, so the 14%
   cross-script matches enter the same blocks as their S1 partner. This is the
   single biggest recall lever most teams will miss. Validate the Devanagari→
   Latin gain empirically first (translit may be phonetically imperfect —
   back it up with address blocking).
3. **Union blocking, address-aware**: name char-trigram TF-IDF (backbone, ~92%)
   ∪ content-token ∪ **address n-gram/number block** to reach the last ~8%
   (esp. cross-script, where name is useless but address still overlaps).
4. **Address-mandatory matcher**: because 19% of S1 names collide, require
   address agreement to confirm a match; treat name-only agreement as weak.
   This is precisely what F_0.5 rewards.
5. **Suffix/generic-token down-weighting via IDF**: `limited/private/llc/...` and
   `services/center/...` are near-stopwords; identity lives in the rare tokens.
6. **Singleton discipline** (5.6% of entities, worth 1.0 each): when the best
   candidate is only name-similar with no address support, prefer emitting empty.
7. **Country-agnostic model features only** (similarity scores, `country_match`
   boolean) so France — unseen in training — behaves like US/India at inference.

## Open questions to resolve empirically (Stage 1)
- Does unidecode transliteration actually raise ASCII↔Devanagari name Jaccard
  enough to block them, or must those rely on address? (measure the lift)
- Combined multi-key blocking recall vs. mean candidates/S1 (the scored
  reduction-ratio trade-off) — find the knee.
- Best address tokenisation for India landmark/PIN-sparse addresses vs. US vs.
  France.

