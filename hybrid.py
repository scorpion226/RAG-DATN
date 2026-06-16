"""
hybrid.py — Truy xuất HYBRID: kết hợp BM25 (từ vựng) + vector (ngữ nghĩa) bằng RRF.

Reciprocal Rank Fusion (RRF): score(d) = Σ 1/(c + rank_d) trên từng bộ truy xuất.
Ưu điểm: không cần chuẩn hoá thang điểm giữa BM25 và cosine, chỉ dùng thứ hạng.

Thêm: nhận diện SỐ HIỆU văn bản trong câu hỏi (vd "15/2023/QH15") -> ưu tiên mạnh các
chunk thuộc đúng văn bản đó (điểm yếu kinh điển của vector search).
"""
import re, pickle
from functools import lru_cache
from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer
import torch
import chromadb
import bm25s

CHROMA_DIR = "chroma_db"; COLLECTION = "legal_medical"
EMBED_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"
BM25_DIR = "bm25_index"; META_PKL = "bm25_meta.pkl"
RRF_C = 60
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
# Mẫu số hiệu VBQPPL VN: 15/2023/QH15, 147/2025/NĐ-CP, 01/2026/TT-BYT, 08/QĐ-QLD...
DOCNUM_RE = re.compile(r"\b\d+\s*/\s*(?:\d{2,4}\s*/\s*)?[A-ZĐ][\w.\-/]*", re.UNICODE)


class HybridRetriever:
    def __init__(self, use_rerank=False, n_each=30, expand=False,
                 embed_model=EMBED_MODEL, collection=COLLECTION, segment=True, fp16=False):
        self.model = SentenceTransformer(embed_model, device=DEVICE, trust_remote_code=True)
        if fp16 and DEVICE == "cuda":
            self.model.half()
        self.segment = segment        # tách từ truy vấn (PhoBERT cần; bge-m3 dùng text thô)
        self.coll = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(collection)
        self.bm25 = bm25s.BM25.load(BM25_DIR)
        with open(META_PKL, "rb") as f:
            self.meta = pickle.load(f)
        self.n_each = n_each
        self.expand = expand          # mở rộng truy vấn bằng từ điển đời thường->pháp lý
        self.reranker = None
        if use_rerank:
            from rerank import Reranker
            self.reranker = Reranker()

    def count(self):
        return self.coll.count()

    def _vector(self, query, n, where):
        seg = ViTokenizer.tokenize(query) if self.segment else query
        emb = self.model.encode([seg], normalize_embeddings=True).tolist()
        r = self.coll.query(query_embeddings=emb, n_results=n, where=where,
                            include=["documents", "metadatas"])
        return [{"chunk_id": i, "text": d, "metadata": m}
                for i, d, m in zip(r["ids"][0], r["documents"][0], r["metadatas"][0])]

    def _bm25(self, query, n, only_effective):
        toks = bm25s.tokenize(query, stopwords=None, show_progress=False)
        idx, _ = self.bm25.retrieve(toks, k=n * 3 if only_effective else n, show_progress=False)
        out = []
        for j in idx[0]:
            m = self.meta[j]
            if only_effective and m.get("effect_status") != "In effect":
                continue
            out.append({"chunk_id": m["chunk_id"], "text": None, "metadata": m})
            if len(out) >= n:
                break
        return out

    def search(self, query, k=5, where=None, only_effective=None):
        if only_effective is None:  # suy ra từ where để đồng bộ giao diện với Retriever
            only_effective = bool(where and where.get("effect_status") == "In effect")
        # Mở rộng truy vấn (đời thường -> pháp lý) chỉ cho khâu TRUY XUẤT;
        # nhận diện số hiệu và rerank vẫn dùng câu hỏi GỐC (giữ đúng ý người dùng).
        qr = query
        if self.expand:
            from query_expand import expand_query
            qr = expand_query(query)
        vec = self._vector(qr, self.n_each, where)
        bm = self._bm25(qr, self.n_each, only_effective)
        # RRF fusion theo chunk_id
        scores, store = {}, {}
        for lst in (vec, bm):
            for rank, h in enumerate(lst):
                cid = h["chunk_id"]
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_C + rank)
                if cid not in store or (store[cid].get("text") is None and h.get("text")):
                    store[cid] = h
        # Ưu tiên số hiệu văn bản nếu câu hỏi có nhắc tới
        for dn in set(DOCNUM_RE.findall(query)):
            dn = dn.strip()
            if not dn:
                continue
            # boost ứng viên sẵn có trùng số hiệu
            for cid, h in store.items():
                if dn in str(h["metadata"].get("document_number", "")):
                    scores[cid] += 1.0
            # tiêm thẳng chunk có ĐÚNG số hiệu từ Chroma (kể cả khi không lọt top ứng viên)
            try:
                g = self.coll.get(where={"document_number": dn}, limit=5,
                                  include=["documents", "metadatas"])
                for cid, doc, m in zip(g["ids"], g["documents"], g["metadatas"]):
                    scores[cid] = scores.get(cid, 0.0) + 1.0
                    store.setdefault(cid, {"chunk_id": cid, "text": doc, "metadata": m})
            except Exception:
                pass
        ranked = sorted(scores, key=scores.get, reverse=True)
        hits = [{"text": store[c]["text"], "score": round(scores[c], 4),
                 "metadata": store[c]["metadata"], "chunk_id": c} for c in ranked]
        # Chỉ xử lý slice cần thiết (rerank thì cần nhiều ứng viên hơn)
        hits = hits[:max(self.n_each, k)] if self.reranker else hits[:k]
        # Điền text còn thiếu (chunk chỉ từ BM25) từ Chroma cho TẤT CẢ hit trong slice
        missing = [h["chunk_id"] for h in hits if h["text"] is None]
        if missing:
            got = self.coll.get(ids=missing, include=["documents"])
            tmap = dict(zip(got["ids"], got["documents"]))
            for h in hits:
                if h["text"] is None:
                    h["text"] = tmap.get(h["chunk_id"], "") or ""
        if self.reranker:
            hits = self.reranker.rerank(query, hits, top_k=k)
        return hits[:k]
