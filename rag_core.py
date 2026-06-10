"""
rag_core.py — Lõi RETRIEVAL của hệ thống RAG.

Quy trình truy vấn (cho báo cáo):
  câu hỏi -> tách từ (pyvi) -> embedding (cùng model lúc index)
          -> tìm top-k cosine trong ChromaDB (kèm lọc metadata)
          -> trả về các chunk + nguồn trích dẫn.

Dùng:
  from rag_core import Retriever
  r = Retriever(); hits = r.search("Thẩm quyền của Sở Y tế?", k=5)
"""
import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

from functools import lru_cache
from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer
import chromadb

CHROMA_DIR = "chroma_db"
COLLECTION = "legal_medical"
EMBED_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"


class Retriever:
    def __init__(self, chroma_dir=CHROMA_DIR, collection=COLLECTION, model=EMBED_MODEL,
                 use_rerank=False, n_candidates=30):
        self.model = SentenceTransformer(model, device="cpu")
        self.client = chromadb.PersistentClient(path=chroma_dir)
        self.coll = self.client.get_collection(collection)
        self.n_candidates = n_candidates
        self.reranker = None
        if use_rerank:
            from rerank import Reranker
            self.reranker = Reranker()

    def count(self):
        return self.coll.count()

    def search(self, query, k=5, where=None):
        """Trả về list dict: {text, score, metadata}. 'where' = lọc metadata Chroma.
        Nếu bật reranker: lấy n_candidates ứng viên rồi xếp lại bằng cross-encoder."""
        seg = ViTokenizer.tokenize(query)
        qemb = self.model.encode([seg], normalize_embeddings=True).tolist()
        n = max(self.n_candidates, k) if self.reranker else k
        res = self.coll.query(query_embeddings=qemb, n_results=n, where=where,
                              include=["documents", "metadatas", "distances"])
        hits = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            hits.append({"text": doc, "score": 1.0 - dist, "metadata": meta})
        if self.reranker:
            hits = self.reranker.rerank(query, hits, top_k=k)
        return hits


def format_context(hits):
    """Ghép các chunk thành context có đánh số nguồn để LLM trích dẫn."""
    blocks = []
    for i, h in enumerate(hits, 1):
        m = h["metadata"]
        src = f"[{i}] {m.get('document_number','?')} — {m.get('title','')}".strip()
        blocks.append(f"{src}\n{h['text']}")
    return "\n\n".join(blocks)


if __name__ == "__main__":
    r = Retriever()
    print(f"Collection có {r.count():,} vector.\n")
    for q in ["Thẩm quyền của Sở Y tế thành phố là gì?",
              "Quy định về phân cấp quản lý dược?",
              "Điều kiện cấp chứng chỉ hành nghề khám chữa bệnh?"]:
        print("="*80); print("HỎI:", q)
        for h in r.search(q, k=3):
            m = h["metadata"]
            print(f"  • score={h['score']:.3f} | {m.get('document_number')} | {m.get('title','')[:55]}")
            print(f"    {h['text'][:140].strip()}...")
        print()
