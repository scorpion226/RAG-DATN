# -*- coding: utf-8 -*-
"""Đánh giá bộ 200 câu: nạp model 1 lần, chấm 5 cấu hình (Hit@k, MRR) + quét P/R/F1@k (1..10)
cho cấu hình Hybrid+Reranker. Dùng đúng các lớp của hệ thống. Lưu eval/eval200.json."""
import sys, os, json, statistics
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


def hits_to_docs(hits):
    return dedup([h["metadata"] for h in hits])


def metrics(ranked_per_q):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(ranked_per_q)
    for docs, rel in ranked_per_q:
        first = next((i + 1 for i, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]):
                hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3)}


def main():
    print("Nạp model (embedder + bm25 + reranker)...")
    r = HybridRetriever(use_rerank=True)
    reranker = r.reranker
    coll, model = r.coll, r.model

    def vec_query(q, segment, n):
        qx = ViTokenizer.tokenize(q) if segment else q
        emb = model.encode([qx], normalize_embeddings=True).tolist()
        res = coll.query(query_embeddings=emb, n_results=n, where=WHERE,
                         include=["documents", "metadatas"])
        return [{"text": d, "metadata": m} for d, m in zip(res["documents"][0], res["metadatas"][0])]

    configs = {"noseg": [], "vector": [], "vector_rr": [], "hybrid": [], "hybrid_rr": []}
    prranked = []  # cho P/R sweep (hybrid_rr)
    for i, it in enumerate(golden):
        rel = set(it["relevant"]); q = it["q"]
        # noseg, vector
        configs["noseg"].append((dedup([h["metadata"] for h in vec_query(q, False, 10)]), rel))
        vec30 = vec_query(q, True, 30)
        configs["vector"].append((dedup([h["metadata"] for h in vec30[:10]]), rel))
        # vector + rerank (xếp lại 30 ứng viên vector)
        vr = reranker.rerank(q, [dict(h) for h in vec30], top_k=10)
        configs["vector_rr"].append((hits_to_docs(vr), rel))
        # hybrid (tắt rerank) & hybrid+rerank
        r.reranker = None
        hyb = r.search(q, k=10, where=WHERE)
        r.reranker = reranker
        configs["hybrid"].append((hits_to_docs(hyb), rel))
        hr = r.search(q, k=10, where=WHERE)
        docs_hr = hits_to_docs(hr)
        configs["hybrid_rr"].append((docs_hr, rel))
        prranked.append((docs_hr, rel))
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(golden)}")

    res = {name: metrics(v) for name, v in configs.items()}
    # P/R/F1 sweep cho hybrid_rr
    avg_rel = statistics.mean(len(it["relevant"]) for it in golden)
    sweep = {}
    for k in range(1, 11):
        P = R = 0.0
        for docs, rel in prranked:
            inter = len(set(docs[:k]) & rel)
            P += inter / k; R += inter / len(rel)
        P /= len(golden); R /= len(golden)
        F1 = (2 * P * R / (P + R)) if (P + R) else 0.0
        sweep[k] = {"P": round(P, 3), "R": round(R, 3), "F1": round(F1, 3),
                    "ceilP": round(min(avg_rel, k) / k, 3)}
    out = {"n": len(golden), "avg_rel": round(avg_rel, 2), "configs": res, "sweep": sweep}
    json.dump(out, open(os.path.join(HERE, "eval200.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n=== Hit@k / MRR (200 câu) ===")
    for name in ["noseg", "vector", "vector_rr", "hybrid", "hybrid_rr"]:
        print(f"  {name:10}", res[name])
    print("✅ Lưu eval200.json")


if __name__ == "__main__":
    main()
