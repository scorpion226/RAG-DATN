# -*- coding: utf-8 -*-
"""Đánh giá NHANH 650 câu cho 3 cấu hình KHÔNG reranker (noseg, vector, hybrid)
+ P/R/F1 sweep cho hybrid. Không nạp reranker nên chạy vài phút. Lưu eval/eval650_fast.json."""
import sys, os, json, statistics, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
from pyvi import ViTokenizer
from hybrid import HybridRetriever

WHERE = {"effect_status": "In effect"}
KS = [1, 3, 5, 10]


def dedup(metas):
    seen = []
    for m in metas:
        dn = m.get("document_number")
        if dn and dn not in seen:
            seen.append(dn)
    return seen


def metrics(rows):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(rows)
    for docs, rel in rows:
        first = next((i + 1 for i, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]):
                hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3), "n": n}


def main():
    t0 = time.time()
    print(f"Nạp embedder + bm25 (KHÔNG reranker)... | {len(golden)} câu")
    r = HybridRetriever(use_rerank=False)
    coll, model = r.coll, r.model

    def vec(q, segment, n):
        qx = ViTokenizer.tokenize(q) if segment else q
        emb = model.encode([qx], normalize_embeddings=True).tolist()
        res = coll.query(query_embeddings=emb, n_results=n, where=WHERE, include=["metadatas"])
        return res["metadatas"][0]

    cfg = {"noseg": [], "vector": [], "hybrid": []}
    # tách riêng theo loại câu để báo cáo nhóm tự nhiên
    by_type = {"manual": {"hybrid": []}, "generated": {"hybrid": []}, "natural": {"hybrid": []}}
    prranked = []
    for i, it in enumerate(golden):
        rel = set(it["relevant"]); q = it["q"]; typ = it.get("type", "manual")
        cfg["noseg"].append((dedup(vec(q, False, 10)), rel))
        cfg["vector"].append((dedup(vec(q, True, 10)), rel))
        hyb = r.search(q, k=10, where=WHERE)         # hybrid (reranker=None)
        docs = dedup([h["metadata"] for h in hyb])
        cfg["hybrid"].append((docs, rel))
        by_type[typ]["hybrid"].append((docs, rel))
        prranked.append((docs, rel))
        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(golden)}  ({time.time()-t0:.0f}s)")

    res = {name: metrics(v) for name, v in cfg.items()}
    res_by_type = {t: metrics(v["hybrid"]) for t, v in by_type.items() if v["hybrid"]}
    avg_rel = statistics.mean(len(it["relevant"]) for it in golden)
    sweep = {}
    for k in range(1, 11):
        P = R = 0.0
        for docs, rel in prranked:
            inter = len(set(docs[:k]) & rel)
            P += inter / k; R += inter / len(rel)
        P /= len(golden); R /= len(golden)
        sweep[k] = {"P": round(P, 3), "R": round(R, 3),
                    "F1": round(2*P*R/(P+R), 3) if (P+R) else 0.0,
                    "ceilP": round(min(avg_rel, k)/k, 3)}
    out = {"n": len(golden), "avg_rel": round(avg_rel, 2), "configs": res,
           "hybrid_by_type": res_by_type, "sweep_hybrid": sweep, "secs": round(time.time()-t0)}
    json.dump(out, open(os.path.join(HERE, "eval650_fast.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n=== Hit@k/MRR (650 câu, không reranker) ===")
    for name in ["noseg", "vector", "hybrid"]:
        print(f"  {name:8}", res[name])
    print("=== Hybrid theo loại câu ===")
    for t, m in res_by_type.items():
        print(f"  {t:10}", m)
    print(f"✅ Lưu eval650_fast.json ({out['secs']}s)")


if __name__ == "__main__":
    main()
