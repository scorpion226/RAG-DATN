# -*- coding: utf-8 -*-
"""Tổng hợp eval_natural_improve.jsonl -> eval_natural_improve.json (Hit@k/MRR cho 4 điều kiện).
Chạy: python eval/aggregate_natural_improve.py"""
import os, json, sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
rel_of = {i: set(q["relevant"]) for i, q in enumerate(golden)}
rows = {}
for line in open(os.path.join(HERE, "eval_natural_improve.jsonl"), encoding="utf-8"):
    try:
        d = json.loads(line); rows[d["idx"]] = d
    except Exception:
        pass
KS = [1, 3, 5, 10]
COND = ["baseline", "dict", "hyde", "dict_hyde"]


def metrics(items):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(items)
    for docs, rel in items:
        first = next((i + 1 for i, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]):
                hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3), "n": n}


idxs = sorted(rows)
res = {c: metrics([(rows[i][c], rel_of[i]) for i in idxs]) for c in COND}
out = {"n_done": len(idxs), "results": res,
       "samples": [{"idx": i, "q": golden[i]["q"], "hyde": rows[i].get("hyde_text", "")[:300]}
                   for i in idxs[:10]]}
json.dump(out, open(os.path.join(HERE, "eval_natural_improve.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"Đã xong {len(idxs)} câu tự nhiên")
for c in COND:
    print(f"  {c:10}", res[c])
print("✅ Lưu eval_natural_improve.json")
