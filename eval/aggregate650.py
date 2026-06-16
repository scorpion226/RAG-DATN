# -*- coding: utf-8 -*-
"""Tổng hợp eval650.jsonl -> eval650.json: Hit@k/MRR cho 5 cấu hình, P/R/F1 sweep (hybrid_rr),
và Hit@k/MRR của hybrid_rr theo loại câu (manual/generated/natural).
Chạy: python eval/aggregate650.py"""
import os, json, sys, statistics
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
rows = {}
for line in open(os.path.join(HERE, "eval650.jsonl"), encoding="utf-8"):
    try:
        d = json.loads(line); rows[d["idx"]] = d
    except Exception: pass
KS = [1, 3, 5, 10]
CFG = ["noseg", "vector", "hybrid", "vector_rr", "hybrid_rr"]


def metrics(items):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(items)
    for docs, rel in items:
        first = next((i + 1 for i, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]): hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k]/n, 3) for k in KS}, "MRR": round(rr/n, 3), "n": n}


idxs = sorted(rows)
res = {}
for c in CFG:
    items = [(rows[i][c], set(golden[i]["relevant"])) for i in idxs]
    res[c] = metrics(items)
# theo loại câu (hybrid_rr)
bytype = {}
for t in ["manual", "generated", "natural"]:
    ids = [i for i in idxs if golden[i].get("type", "manual") == t]
    if ids:
        bytype[t] = metrics([(rows[i]["hybrid_rr"], set(golden[i]["relevant"])) for i in ids])
# P/R/F1 sweep cho hybrid_rr
avg_rel = statistics.mean(len(golden[i]["relevant"]) for i in idxs)
sweep = {}
for k in range(1, 11):
    P = R = 0.0
    for i in idxs:
        docs = rows[i]["hybrid_rr"]; rel = set(golden[i]["relevant"])
        inter = len(set(docs[:k]) & rel); P += inter/k; R += inter/len(rel)
    P /= len(idxs); R /= len(idxs)
    sweep[k] = {"P": round(P, 3), "R": round(R, 3), "F1": round(2*P*R/(P+R), 3) if (P+R) else 0,
                "ceilP": round(min(avg_rel, k)/k, 3)}
out = {"n_done": len(idxs), "n_total": len(golden), "avg_rel": round(avg_rel, 2),
       "configs": res, "by_type_hybrid_rr": bytype, "sweep_hybrid_rr": sweep}
json.dump(out, open(os.path.join(HERE, "eval650.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"Đã xong {len(idxs)}/{len(golden)} câu")
for c in CFG: print(f"  {c:10}", res[c])
print("Theo loại (hybrid_rr):")
for t, m in bytype.items(): print(f"  {t:10}", m)
print("✅ Lưu eval650.json")
