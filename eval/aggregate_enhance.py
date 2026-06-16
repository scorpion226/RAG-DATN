# -*- coding: utf-8 -*-
"""Tổng hợp eval_enhance.jsonl + tái dùng baseline/dict từ eval_natural_improve.jsonl.
Chạy: python eval/aggregate_enhance.py"""
import os, json, sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
rel = {i: set(q["relevant"]) for i, q in enumerate(golden)}
KS = [1, 3, 5, 10]


def metrics(items):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(items)
    for docs, r in items:
        first = next((j + 1 for j, dn in enumerate(docs) if dn in r), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in r for dn in docs[:k]): hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3), "n": n}


def load(path, keys):
    rows = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            try:
                d = json.loads(line); rows[d["idx"]] = d
            except Exception: pass
    return rows


base = load(os.path.join(HERE, "eval_natural_improve.jsonl"), None)   # có 'baseline','dict'
enh = load(os.path.join(HERE, "eval_enhance.jsonl"), None)
idxs = sorted(enh)
res = {}
if base:
    bi = [i for i in sorted(base)]
    res["baseline"] = metrics([(base[i]["baseline"], rel[i]) for i in bi])
    res["dict (append)"] = metrics([(base[i]["dict"], rel[i]) for i in bi])
for c in ["dict_norm_mined", "dict_rm3", "dict_rm3_norm_mined"]:
    if idxs:
        res[c] = metrics([(enh[i][c], rel[i]) for i in idxs])
json.dump(res, open(os.path.join(HERE, "eval_enhance.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"Số câu enhance: {len(idxs)}")
for c, m in res.items():
    print(f"  {c:22}", m)
print("✅ Lưu eval_enhance.json")
