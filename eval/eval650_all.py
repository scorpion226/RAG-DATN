# -*- coding: utf-8 -*-
"""Đánh giá 650 câu, CẢ 5 cấu hình, RESUME ĐƯỢC (ghi từng câu vào eval650.jsonl).
Mỗi câu lưu ranked doc của: noseg, vector, hybrid, vector_rr, hybrid_rr.
Chạy lại sẽ bỏ qua câu đã xong. Nên chạy DETACHED (Start-Process) để sống sót qua ngủ máy.
Chạy: python eval/eval650_all.py"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
JSONL = os.path.join(HERE, "eval650.jsonl")
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
            try: done.add(json.loads(line)["idx"])
            except Exception: pass
    print(f"Đã xong {len(done)}/{len(golden)}. Nạp model...", flush=True)
    r = HybridRetriever(use_rerank=True)
    reranker = r.reranker; coll, model = r.coll, r.model

    with open(JSONL, "a", encoding="utf-8") as f:
        for i, it in enumerate(golden):
            if i in done:
                continue
            q = it["q"]
            # noseg
            e0 = model.encode([q], normalize_embeddings=True).tolist()
            noseg = dedup(coll.query(query_embeddings=e0, n_results=10, where=WHERE,
                                     include=["metadatas"])["metadatas"][0])
            # vector top-30 (segment)
            e1 = model.encode([ViTokenizer.tokenize(q)], normalize_embeddings=True).tolist()
            vres = coll.query(query_embeddings=e1, n_results=30, where=WHERE,
                              include=["documents", "metadatas"])
            vector = dedup(vres["metadatas"][0][:10])
            vcand = [{"text": d, "metadata": m} for d, m in zip(vres["documents"][0], vres["metadatas"][0])]
            vector_rr = dedup([h["metadata"] for h in reranker.rerank(q, [dict(h) for h in vcand], top_k=10)])
            # hybrid (no rerank)
            r.reranker = None
            hybrid = dedup([h["metadata"] for h in r.search(q, k=10, where=WHERE)])
            r.reranker = reranker
            # hybrid + rerank
            hybrid_rr = dedup([h["metadata"] for h in r.search(q, k=10, where=WHERE)])
            f.write(json.dumps({"idx": i, "noseg": noseg, "vector": vector, "hybrid": hybrid,
                                "vector_rr": vector_rr, "hybrid_rr": hybrid_rr}, ensure_ascii=False) + "\n")
            f.flush()
            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{len(golden)}", flush=True)
    print("✅ Hoàn tất. Chạy: python eval/aggregate650.py", flush=True)


if __name__ == "__main__":
    main()
