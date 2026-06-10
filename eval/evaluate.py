"""
evaluate.py — Đánh giá định lượng chất lượng RETRIEVAL của hệ thống RAG.

Ground-truth: mỗi câu hỏi được điều chỉnh bởi (các) văn bản luật cụ thể -> coi số hiệu
luật đó là văn bản "liên quan". Đo retriever có tìm đúng văn bản đó trong top-k không.

Chỉ số:
  - Hit@k : tỷ lệ câu hỏi có >=1 văn bản liên quan trong top-k (recall mức câu hỏi).
  - MRR   : trung bình nghịch đảo thứ hạng của văn bản liên quan đầu tiên (chất lượng xếp hạng).

A/B: thêm cờ --no-segment để truy vấn KHÔNG tách từ (so với mặc định có pyvi) -> chứng minh
tầm quan trọng của việc tách từ nhất quán giữa index và truy vấn.

Chạy:  python eval/evaluate.py
       python eval/evaluate.py --no-segment        # nhánh B (không tách từ)
"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer
import chromadb

CHROMA_DIR = "chroma_db"
COLLECTION = "legal_medical"
EMBED_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"
KS = [1, 3, 5, 10]


def _golden():
    here = os.path.dirname(os.path.abspath(__file__))
    return json.load(open(os.path.join(here, "golden_questions.json"), encoding="utf-8"))


def _report(name, ranked_per_q, golden):
    hits_at = {k: 0 for k in KS}; rr = 0.0; n = len(golden)
    for ranked, item in zip(ranked_per_q, golden):
        rel = set(item["relevant"])
        first = next((i + 1 for i, dn in enumerate(ranked) if dn in rel), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in ranked[:k]):
                hits_at[k] += 1
    print(f"\n=== KẾT QUẢ ({name}) ===")
    for k in KS:
        print(f"  Hit@{k:<2} = {hits_at[k]/n:.3f}  ({hits_at[k]}/{n})")
    print(f"  MRR    = {rr/n:.3f}")


def run_hybrid(args):
    from hybrid import HybridRetriever
    golden = _golden()
    h = HybridRetriever(use_rerank=args.rerank)
    name = "hybrid+rerank" if args.rerank else "hybrid"
    print(f"Đánh giá {len(golden)} câu | chế độ: {name}\n")
    ranked_per_q = []
    for item in golden:
        hits = h.search(item["q"], k=args.k, only_effective=True)
        ranked = [x["metadata"].get("document_number") for x in hits]
        ranked_per_q.append(ranked)
        rel = set(item["relevant"])
        first = next((i + 1 for i, dn in enumerate(ranked) if dn in rel), None)
        print(f"  [{('#'+str(first)) if first else 'MISS':>5}] {item['q'][:56]:56} → {ranked[0] if ranked else '-'}")
    _report(name, ranked_per_q, golden)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-segment", action="store_true", help="Truy vấn không tách từ (nhánh B)")
    ap.add_argument("--k", type=int, default=10, help="Số kết quả lấy về để chấm")
    ap.add_argument("--rerank", action="store_true", help="Bật reranker cross-encoder (lấy 30 ứng viên rồi xếp lại)")
    ap.add_argument("--hybrid", action="store_true", help="Dùng hybrid BM25+vector (RRF) thay cho vector thuần")
    args = ap.parse_args()

    if args.hybrid:
        return run_hybrid(args)

    reranker = None
    n_cand = args.k
    if args.rerank:
        from rerank import Reranker
        reranker = Reranker()
        n_cand = max(30, args.k)   # lấy nhiều ứng viên cho reranker chọn

    here = os.path.dirname(os.path.abspath(__file__))
    golden = json.load(open(os.path.join(here, "golden_questions.json"), encoding="utf-8"))

    model = SentenceTransformer(EMBED_MODEL, device="cpu")
    coll = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION)
    mode = "KHÔNG tách từ" if args.no_segment else "CÓ tách từ (pyvi)"
    print(f"Đánh giá {len(golden)} câu hỏi | chế độ: {mode} | index {coll.count():,} vector\n")

    hits_at = {k: 0 for k in KS}
    rr_sum = 0.0
    for item in golden:
        q = item["q"]; rel = set(item["relevant"])
        qx = q if args.no_segment else ViTokenizer.tokenize(q)
        emb = model.encode([qx], normalize_embeddings=True).tolist()
        res = coll.query(query_embeddings=emb, n_results=n_cand,
                         include=["metadatas", "documents"])
        if reranker:
            cand = [{"text": d, "metadata": m}
                    for d, m in zip(res["documents"][0], res["metadatas"][0])]
            cand = reranker.rerank(q, cand, top_k=args.k)
            ranked = [h["metadata"].get("document_number") for h in cand]
        else:
            ranked = [m.get("document_number") for m in res["metadatas"][0]][:args.k]
        # thứ hạng đầu tiên trúng văn bản liên quan
        first = next((i + 1 for i, dn in enumerate(ranked) if dn in rel), None)
        rr_sum += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in ranked[:k]):
                hits_at[k] += 1
        mark = f"#{first}" if first else "MISS"
        print(f"  [{mark:>5}] {q[:58]:58} → {ranked[0]}")

    n = len(golden)
    print("\n=== KẾT QUẢ ===")
    for k in KS:
        print(f"  Hit@{k:<2} = {hits_at[k]/n:.3f}  ({hits_at[k]}/{n})")
    print(f"  MRR    = {rr_sum/n:.3f}")


if __name__ == "__main__":
    main()
