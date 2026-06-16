"""
rerank.py — Reranker (cross-encoder PhoRanker) đặt SAU bi-encoder.

Vì sao cần (cho báo cáo): bi-encoder mã hoá câu hỏi & đoạn ĐỘC LẬP rồi so cosine -> nhanh
nhưng kém tinh tế. Cross-encoder đọc ĐỒNG THỜI (câu hỏi + đoạn) nên chấm độ liên quan
chính xác hơn -> dùng để xếp lại top-N ứng viên, thường tăng Hit@1 & MRR.

PhoRanker dựa trên PhoBERT -> đầu vào cũng cần tách từ (pyvi), giống bi-encoder.
"""
from pyvi import ViTokenizer
from sentence_transformers import CrossEncoder
import torch

RERANK_MODEL = "itdainb/PhoRanker"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


class Reranker:
    def __init__(self, model_name=RERANK_MODEL, max_length=256, device=None):
        self.model = CrossEncoder(model_name, max_length=max_length,
                                  device=device or DEVICE)

    def rerank(self, query, hits, top_k=None):
        """hits: list dict có 'text' & 'metadata'. Trả về hits sắp xếp lại theo điểm cross-encoder."""
        if not hits:
            return hits
        qx = ViTokenizer.tokenize(query)
        pairs = [[qx, ViTokenizer.tokenize(h["text"])] for h in hits]
        scores = self.model.predict(pairs)
        for h, s in zip(hits, scores):
            h["rerank_score"] = float(s)
        ranked = sorted(hits, key=lambda h: h["rerank_score"], reverse=True)
        return ranked[:top_k] if top_k else ranked
