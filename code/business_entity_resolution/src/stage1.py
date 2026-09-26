"""Stage 1 — recall-first blocking engine (the 0.52 -> >=0.95 unlock).

Blocking is a UNION of complementary keys, all strictly within country:
  A. exact `name_core`            (Stage 0 key; highest precision)
  B. char n-gram (3-4) TF-IDF     (recall backbone; EDA: 91.8% share a trigram)
  C. [next iteration] address block for the cross-script tail

Everything runs one COUNTRY partition at a time so memory stays bounded (the
biggest partition, ~half of the 10M S2/S3, fits well under 16.8 GB). We use a
HashingVectorizer (no giant vocab dict at 4M+ names) and fold IDF back in from
document frequencies, pruning the highest-DF n-grams (not discriminative, and
they dominate the matmul cost).

This module measures BLOCKING RECALL only. Per the plan, recall >= 0.95 on the
holdout is the gate to advance; the scorer (Stage 1b / Stage 2) comes after.

Usage:
  python stage1.py val --train-dir ../../../dataset/train --sample 20000 --topk 20
"""
import argparse
import os
import sys
import time
import random

import numpy as np
import pandas as pd
from scipy.sparse import diags
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import clean, name_core, name_tokens, addr_tokens  # noqa: E402

CHUNK = 400_000
N_FEATURES = 2 ** 20


def make_vectorizer():
    """Word-level TF over name+address tokens (unigrams+bigrams).

    EDA/diag: a content-token UNION address-token blocker has a 1.00 recall
    ceiling; char n-grams plateaued at ~0.74 (ignored address, truncated top-k).
    Word tokens are far more selective and let address carry the ~14% cross-
    script matches whose romanised name shares nothing.
    """
    return HashingVectorizer(analyzer="word", ngram_range=(1, 2),
                             n_features=N_FEATURES, alternate_sign=False, norm=None)


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_s1_sample(train_dir, sample, seed=7):
    """Sample S1 from GT; return true_map and {country: [(id, text, core)]}.

    `text` = clean(name) + " " + clean(address) — the blocking vector bag.
    """
    gt = pd.read_csv(os.path.join(train_dir, "train_ground_truth.tsv"),
                     sep="\t", dtype=str, na_filter=False)
    random.seed(seed)
    idx = random.sample(range(len(gt)), min(sample, len(gt)))
    samp = gt.iloc[idx]
    true_map = {s1: (set(m.split(",")) if m.strip() else set())
                for s1, m in zip(samp["source1_entity_id"], samp["matched_entity_ids"])}
    keep = set(true_map)
    by_country = {}
    for ch in pd.read_csv(os.path.join(train_dir, "train_source1.tsv"),
                          sep="\t", dtype=str, na_filter=False, chunksize=CHUNK):
        ch = ch[ch["entity_id"].isin(keep)]
        for eid, nm, ad, ctry in zip(ch["entity_id"], ch["business_name"],
                                     ch["business_address"], ch["country"]):
            by_country.setdefault(ctry, []).append(
                (eid, clean(nm) + " " + clean(ad), name_core(nm)))
    return true_map, by_country


def load_pools(paths, countries):
    """ONE streaming pass over S2/S3; partition needed countries' rows.

    Returns {country: (ids, texts, cores)} where text = clean(name)+" "+clean(addr).
    Re-streaming per country would be N full passes over 10M rows; this is one
    pass, memory-bounded to the sampled countries (dominated by a few per EDA).
    """
    pools = {c: ([], [], []) for c in countries}
    scanned = 0
    for path in paths:
        for ch in pd.read_csv(path, sep="\t", dtype=str, na_filter=False, chunksize=CHUNK):
            scanned += len(ch)
            ch = ch[ch["country"].isin(countries)]
            for eid, nm, ad, ctry in zip(ch["entity_id"], ch["business_name"],
                                         ch["business_address"], ch["country"]):
                ids, texts, cores = pools[ctry]
                ids.append(eid)
                texts.append(clean(nm) + " " + clean(ad))
                cores.append(name_core(nm))
        _log(f"  scanned {scanned:,} rows")
    return pools



def _vectorize(texts, vec):
    """TF matrix -> IDF-weighted, high-DF pruned, l2-normalized (returns M, idf)."""
    M = vec.transform(texts)
    df = np.asarray((M > 0).sum(axis=0)).ravel()
    N = M.shape[0]
    idf = np.zeros(N_FEATURES, dtype=np.float32)
    nz = df > 0
    idf[nz] = (np.log(N / df[nz]) + 1.0).astype(np.float32)
    idf[df > 0.30 * N] = 0.0          # drop the least-discriminative, costliest tokens
    M = normalize(M @ diags(idf), norm="l2", axis=1, copy=False)
    return M, idf


def topk_candidates(q_texts, M, pool_ids, idf, topk, qchunk=512):
    """For each query, return pool ids of its top-k cosine neighbours (best first)."""
    hv = make_vectorizer()
    Q = normalize(hv.transform(q_texts) @ diags(idf), norm="l2", axis=1, copy=False)
    Mt = M.T.tocsr()
    out = []
    for start in range(0, Q.shape[0], qchunk):
        S = (Q[start:start + qchunk] @ Mt).tocsr()
        for i in range(S.shape[0]):
            lo, hi = S.indptr[i], S.indptr[i + 1]
            if hi == lo:
                out.append([])
                continue
            data, cols = S.data[lo:hi], S.indices[lo:hi]
            if hi - lo > topk:
                part = np.argpartition(data, -topk)[-topk:]
                part = part[np.argsort(data[part])[::-1]]        # best first
            else:
                part = np.argsort(data)[::-1]
            out.append([pool_ids[cols[j]] for j in part])
    return out


def _recall(cand_map, true_map, ids):
    tot = 0.0
    for s1 in ids:
        true = true_map.get(s1, set())
        if not true:
            tot += 1.0
            continue
        tot += len(set(cand_map.get(s1, [])) & true) / len(true)
    return tot / len(ids)


def run_val(args):
    paths = [os.path.join(args.train_dir, "train_source2.tsv"),
             os.path.join(args.train_dir, "train_source3.tsv")]
    true_map, by_country = load_s1_sample(args.train_dir, args.sample)
    ids = [s1 for recs in by_country.values() for s1, _, _ in recs]
    _log(f"sample: {len(ids):,} S1 across {len(by_country)} countries")

    cand_fuzzy, exact_map = {}, {}
    vec = make_vectorizer()
    _log("loading S2/S3 country pools (one pass)...")
    pools = load_pools(paths, set(by_country))
    for ci, (country, recs) in enumerate(
            sorted(by_country.items(), key=lambda kv: -len(kv[1])), 1):
        t0 = time.time()
        pool_ids, pool_names, pool_cores = pools[country]
        if not pool_ids:
            for s1, _, _ in recs:
                exact_map[s1], cand_fuzzy[s1] = [], []
            continue
        core_idx = {}
        for pid, pc in zip(pool_ids, pool_cores):
            if pc:
                core_idx.setdefault(pc, []).append(pid)
        M, idf = _vectorize(pool_names, vec)
        fuzzy = topk_candidates([n for _, n, _ in recs], M, pool_ids, idf, args.topk)
        for (s1, _, core), fz in zip(recs, fuzzy):
            exact_map[s1] = core_idx.get(core, [])
            cand_fuzzy[s1] = fz
        pools[country] = None  # free
        _log(f"  [{ci}/{len(by_country)}] {country!r}: pool={len(pool_ids):,} "
             f"S1={len(recs):,} {time.time()-t0:.1f}s")

    r_exact = _recall(exact_map, true_map, ids)
    _log(f"exact-core recall={r_exact:.4f} (sanity vs Stage 0 ~0.52)")
    print(f"\n  K   union_recall  mean_cand/S1")
    for k in [10, 20, 40, 80]:
        if k > args.topk:
            break
        cm = {s1: list(dict.fromkeys(exact_map[s1] + cand_fuzzy[s1][:k])) for s1 in ids}
        r = _recall(cm, true_map, ids)
        mc = sum(len(v) for v in cm.values()) / len(ids)
        flag = "  <-- PASS>=0.95" if r >= 0.95 else ""
        print(f"  {k:<3} {r:0.4f}        {mc:0.1f}{flag}")


def run_diag(args):
    """Measure the REACHABLE recall ceiling per blocking signal (no ranking/cap).

    For each true match, ask: could a blocker keyed on this signal ever retrieve
    it? This is the upper bound each key contributes — tells us which keys to
    build to clear the 0.95 gate, before spending effort ranking/capping them.
    """
    gt = pd.read_csv(os.path.join(args.train_dir, "train_ground_truth.tsv"),
                     sep="\t", dtype=str, na_filter=False)
    random.seed(7)
    idx = random.sample(range(len(gt)), min(args.sample, len(gt)))
    samp = gt.iloc[idx]
    true_map = {s1: (set(m.split(",")) if m.strip() else set())
                for s1, m in zip(samp["source1_entity_id"], samp["matched_entity_ids"])}
    target = set().union(*true_map.values()) if true_map else set()
    keep_s1 = set(true_map)
    _log(f"diag sample: {len(keep_s1):,} S1, {len(target):,} true-match ids to locate")

    s1feat = {}
    for ch in pd.read_csv(os.path.join(args.train_dir, "train_source1.tsv"),
                          sep="\t", dtype=str, na_filter=False, chunksize=CHUNK):
        ch = ch[ch["entity_id"].isin(keep_s1)]
        for eid, nm, ad in zip(ch["entity_id"], ch["business_name"], ch["business_address"]):
            s1feat[eid] = (name_tokens(nm), addr_tokens(ad), name_core(nm))

    pfeat = {}
    scanned = 0
    for path in (os.path.join(args.train_dir, "train_source2.tsv"),
                 os.path.join(args.train_dir, "train_source3.tsv")):
        for ch in pd.read_csv(path, sep="\t", dtype=str, na_filter=False, chunksize=CHUNK):
            scanned += len(ch)
            ch = ch[ch["entity_id"].isin(target)]
            for eid, nm, ad in zip(ch["entity_id"], ch["business_name"], ch["business_address"]):
                cross = any(ord(c) > 127 for c in nm)
                pfeat[eid] = (name_tokens(nm), addr_tokens(ad), name_core(nm), cross)
        _log(f"  scanned {scanned:,}")
    _log(f"located {len(pfeat):,}/{len(target):,} true-match records")
    _diag_tally(true_map, s1feat, pfeat)


def _diag_tally(true_map, s1feat, pfeat):
    hits = {k: 0 for k in ("exact_core", "name_tok", "addr_tok", "num_tok",
                           "name_or_addr", "cross_script", "total")}
    for s1, trues in true_map.items():
        sf = s1feat.get(s1)
        if not sf:
            continue
        s_ntok, s_atok, s_core = sf
        s_num = {t for t in s_atok if t.isdigit()}
        for tid in trues:
            pf = pfeat.get(tid)
            hits["total"] += 1
            if not pf:
                continue
            p_ntok, p_atok, p_core, cross = pf
            p_num = {t for t in p_atok if t.isdigit()}
            share_name = bool(s_ntok & p_ntok)
            share_addr = bool(s_atok & p_atok)
            if s_core and s_core == p_core:
                hits["exact_core"] += 1
            if share_name:
                hits["name_tok"] += 1
            if share_addr:
                hits["addr_tok"] += 1
            if s_num & p_num:
                hits["num_tok"] += 1
            if share_name or share_addr:
                hits["name_or_addr"] += 1
            if cross:
                hits["cross_script"] += 1
    tot = hits["total"] or 1
    print("\n  signal            reachable-recall ceiling")
    for k in ("exact_core", "name_tok", "addr_tok", "num_tok", "name_or_addr", "cross_script"):
        print(f"  {k:<16} {hits[k]/tot:0.4f}  ({hits[k]:,}/{tot:,})")
    print("  (name_or_addr = union ceiling of a content-token + address-token blocker)")


def selfcheck():
    """Tiny synthetic check: the true partner must rank in a query's top-k."""
    pool_ids = ["S2-1", "S2-2", "S2-3", "S2-4"]
    pool_txt = ["acme steel works 12 main road pune",   # true partner of query
                "globex trading 5 park street mumbai",
                "initech systems 9 hill road delhi",
                "umbrella corp 77 lake avenue chennai"]
    vec = make_vectorizer()
    M, idf = _vectorize(pool_txt, vec)
    q = ["acme steel 12 main road pune"]               # noisy variant of S2-1
    got = topk_candidates(q, M, pool_ids, idf, topk=2)
    assert got[0][0] == "S2-1", got
    assert _recall({"a": ["S2-1"]}, {"a": {"S2-1"}}, ["a"]) == 1.0
    assert _recall({"a": []}, {"a": set()}, ["a"]) == 1.0        # empty-true -> 1.0
    print("stage1.selfcheck OK")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    sub.add_parser("selfcheck")
    v = sub.add_parser("val")
    v.add_argument("--train-dir", default="../../../dataset/train")
    v.add_argument("--sample", type=int, default=20_000)
    v.add_argument("--topk", type=int, default=20)
    d = sub.add_parser("diag")
    d.add_argument("--train-dir", default="../../../dataset/train")
    d.add_argument("--sample", type=int, default=5_000)
    args = ap.parse_args()
    if args.mode == "selfcheck":
        selfcheck()
    elif args.mode == "val":
        run_val(args)
    elif args.mode == "diag":
        run_diag(args)


if __name__ == "__main__":
    main()
