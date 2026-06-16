# -*- coding: utf-8 -*-
"""Đánh giá 2 cấu hình có RERANKER (vector_rr, hybrid_rr) trên 650 câu — RESUME ĐƯỢC.
Ghi từng câu vào eval/eval650_rerank.jsonl (append). Chạy lại sẽ bỏ qua câu đã xong.
Chạy: python eval/eval650_rerank.py    (nên chạy detached để sống sót qua ngủ máy)"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
JSONL = os.path.join(HERE, "eval650_rerank.jsonl")
WHERE = {"effect_status": "In effect"}

from pyvi import ViTokenizer
from hybrid import HybridRetriever


def dedup(metas):
    seen = []
    for m in metas:
        dn = m.get("document_number")
        if dn and dn not in seen:
            seen.append(dn)
    return seen


def main():
    done = set()
    if os.path.exists(JSONL):
        for line in open(JSONL, encoding="utf-8"):
            try:
                done.add(json.loads(line)["idx"])
            except Exception:
                pass
    print(f"Đã xong {len(done)}/{len(golden)} câu. Nạp model...", flush=True)
    r = HybridRetriever(use_rerank=True)
    reranker = r.reranker; coll, model = r.coll, r.model

    with open(JSONL, "a", encoding="utf-8") as f:
        for i, it in enumerate(golden):
            if i in done:
                continue
            q = it["q"]
            # vector top-30 -> rerank
            emb = model.encode([ViTokenizer.tokenize(q)], normalize_embeddings=True).tolist()
            vres = coll.query(query_embeddings=emb, n_results=30, where=WHERE,
                              include=["documents", "metadatas"])
            vcand = [{"text": d, "metadata": m} for d, m in zip(vres["documents"][0], vres["metadatas"][0])]
            vrr = dedup([h["metadata"] for h in reranker.rerank(q, [dict(h) for h in vcand], top_k=10)])
            # hybrid + rerank
            hrr = dedup([h["metadata"] for h in r.search(q, k=10, where=WHERE)])
            f.write(json.dumps({"idx": i, "vector_rr": vrr, "hybrid_rr": hrr}, ensure_ascii=False) + "\n")
            f.flush()
            if (i + 1) % 20 == 0:
                print(f"  {i+1}/{len(golden)}", flush=True)
    print("✅ Hoàn tất tất cả câu. Chạy eval/aggregate650.py để tổng hợp.", flush=True)


if __name__ == "__main__":
    main()
