"""Stage 0 — deterministic, precision-first baseline.

Blocking : within-country exact match on `name_core` (sorted, suffix-stripped).
Matching : keep a candidate when address token Jaccard >= tau.
Rationale: exact core-name + address agreement is high precision; the address
gate defends against the 19% of S1 that share a core name with a different
business (see context/dataset_analysis.md). Recall ceiling ~44% by design —
this is the floor we ship first, then climb in later stages.

Usage:
  python stage0.py val  --train-dir ../../../dataset/train [--sample 50000]
  python stage0.py run  --test-dir  ../../../dataset/test  --out-dir ../../../output --tau 0.3
"""
import argparse
import os
import sys
import time
import random

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from normalize import name_core, addr_tokens  # noqa: E402
from metric import macro_f_beta  # noqa: E402

CHUNK = 400_000


def _log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter) if inter else 0.0


def load_s1(path, keep_ids=None):
    """Return {s1_id: (country, core, addr_tok)} and the id list in file order."""
    s1 = {}
    order = []
    for ch in pd.read_csv(path, sep="\t", dtype=str, na_filter=False, chunksize=CHUNK):
        if keep_ids is not None:
            ch = ch[ch["entity_id"].isin(keep_ids)]
        for eid, nm, ad, ctry in zip(ch["entity_id"], ch["business_name"],
                                     ch["business_address"], ch["country"]):
            s1[eid] = (ctry, name_core(nm), addr_tokens(ad))
            order.append(eid)
    return s1, order


def build_index(paths, needed_keys, cap):
    """Stream S2/S3, keep only records whose (country, core) hits a needed key.

    Returns {(country, core): [(id, addr_tok), ...]} capped at `cap` per bucket.
    """
    index = {}
    kept = scanned = 0
    for path in paths:
        for ch in pd.read_csv(path, sep="\t", dtype=str, na_filter=False, chunksize=CHUNK):
            scanned += len(ch)
            for eid, nm, ad, ctry in zip(ch["entity_id"], ch["business_name"],
                                         ch["business_address"], ch["country"]):
                core = name_core(nm)
                if not core:
                    continue
                key = (ctry, core)
                bucket = index.get(key)
                if bucket is None:
                    if key not in needed_keys:
                        continue
                    bucket = index[key] = []
                if len(bucket) < cap:
                    bucket.append((eid, addr_tokens(ad)))
                    kept += 1
            _log(f"  indexed {os.path.basename(path)}: scanned {scanned:,}, kept {kept:,}")
    return index


def predict(s1_map, index, tau):
    """Return (cand_map, pred_map): candidates per S1 and matches passing tau."""
    cand_map, pred_map = {}, {}
    for s1, (ctry, core, atok) in s1_map.items():
        bucket = index.get((ctry, core)) if core else None
        if not bucket:
            cand_map[s1] = []
            pred_map[s1] = set()
            continue
        cand_map[s1] = [cid for cid, _ in bucket]
        pred_map[s1] = {cid for cid, cad in bucket if jaccard(atok, cad) >= tau}
    return cand_map, pred_map


def _block_recall(cand_map, true_map, ids):
    """Macro recall of the candidate set (ceiling any matcher can reach)."""
    tot = 0.0
    for s1 in ids:
        true = true_map.get(s1, set())
        if not true:
            tot += 1.0
            continue
        tot += len(set(cand_map.get(s1, [])) & true) / len(true)
    return tot / len(ids)


def run_val(args):
    tdir = args.train_dir
    gt = pd.read_csv(os.path.join(tdir, "train_ground_truth.tsv"),
                     sep="\t", dtype=str, na_filter=False)
    random.seed(7)
    idx = random.sample(range(len(gt)), min(args.sample, len(gt)))
    samp = gt.iloc[idx]
    true_map = {s1: (set(m.split(",")) if m.strip() else set())
                for s1, m in zip(samp["source1_entity_id"], samp["matched_entity_ids"])}
    ids = list(true_map)
    _log(f"validation sample: {len(ids):,} S1 entities")

    s1_map, _ = load_s1(os.path.join(tdir, "train_source1.tsv"), keep_ids=set(ids))
    needed = {(c, core) for c, core, _ in s1_map.values() if core}
    _log(f"needed blocking keys: {len(needed):,}")
    index = build_index(
        [os.path.join(tdir, "train_source2.tsv"), os.path.join(tdir, "train_source3.tsv")],
        needed, args.cap)
    _log(f"index buckets: {len(index):,}")

    cand_map, _ = predict(s1_map, index, tau=0.0)
    brecall = _block_recall(cand_map, true_map, ids)
    mean_cand = sum(len(v) for v in cand_map.values()) / len(ids)
    _log(f"BLOCKING: macro-recall={brecall:.4f}  mean candidates/S1={mean_cand:.2f}")

    print("\n  tau   macroF0.5")
    best = (0.0, -1.0)
    for tau in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
        _, pred_map = predict(s1_map, index, tau)
        f = macro_f_beta(pred_map, true_map, ids)
        print(f"  {tau:0.2f}   {f:0.4f}")
        if f > best[1]:
            best = (tau, f)
    _log(f"BEST tau={best[0]:.2f}  F0.5={best[1]:.4f}  (blocking ceiling {brecall:.4f})")


def _write_tsv(path, header_col, order, id_lists):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(f"source1_entity_id\t{header_col}\n")
        for s1 in order:
            f.write(f"{s1}\t{','.join(id_lists.get(s1, []))}\n")


def run_test(args):
    tdir = args.test_dir
    os.makedirs(args.out_dir, exist_ok=True)
    s1_map, order = load_s1(os.path.join(tdir, "test_source1.tsv"))
    _log(f"test S1 loaded: {len(order):,}")
    needed = {(c, core) for c, core, _ in s1_map.values() if core}
    _log(f"needed blocking keys: {len(needed):,}")
    index = build_index(
        [os.path.join(tdir, "test_source2.tsv"), os.path.join(tdir, "test_source3.tsv")],
        needed, args.cap)
    _log(f"index buckets: {len(index):,}")

    cand_map, pred_map = predict(s1_map, index, args.tau)
    n_match = sum(1 for v in pred_map.values() if v)
    _log(f"S1 with >=1 match: {n_match:,} ({100*n_match/len(order):.1f}%)")

    _write_tsv(os.path.join(args.out_dir, "candidate_pairs.tsv"),
               "candidate_entity_ids", order, {k: v for k, v in cand_map.items()})
    _write_tsv(os.path.join(args.out_dir, "matching_results.tsv"),
               "matched_entity_ids", order, {k: sorted(v) for k, v in pred_map.items()})
    _log(f"wrote outputs to {args.out_dir}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    v = sub.add_parser("val")
    v.add_argument("--train-dir", default="../../../dataset/train")
    v.add_argument("--sample", type=int, default=50_000)
    v.add_argument("--cap", type=int, default=300)
    r = sub.add_parser("run")
    r.add_argument("--test-dir", default="../../../dataset/test")
    r.add_argument("--out-dir", default="../../../output")
    r.add_argument("--tau", type=float, default=0.3)
    r.add_argument("--cap", type=int, default=300)
    args = ap.parse_args()
    (run_val if args.mode == "val" else run_test)(args)


if __name__ == "__main__":
    main()
