"""
app.py — Backend FastAPI cho chatbot RAG tra cứu văn bản pháp luật/y tế.

Chạy:  uvicorn app:app --reload --port 8000
  rồi mở http://localhost:8000
Đổi LLM: đặt biến môi trường LLM_MODE=phogpt (mặc định "mock" để test nhanh).

Endpoint:
  GET  /            -> giao diện chat
  POST /chat        -> {question, k, only_effective} -> {answer, sources}
  GET  /health      -> trạng thái + số vector trong index
"""
import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rag_core import Retriever, format_context
from llm import get_llm

app = FastAPI(title="RAG Pháp luật/Y tế VN")
_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=_STATIC), name="static")
_retriever = None
_llm = None


def _flag(name):
    return os.environ.get(name, "0") in ("1", "true", "True")


def retriever():
    global _retriever
    if _retriever is None:
        use_rerank = _flag("USE_RERANK")
        if _flag("USE_BGE"):
            # Cấu hình tốt nhất toàn cục (Mục 4.16–4.17): bge-m3 vector + từ điển + mở rộng
            # ngữ nghĩa + RERANKER FINE-TUNE (PhoRanker). Cần collection bge_m3 + models/ft-reranker-bge.
            _ft = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "ft-reranker-bge")
            _has_ft = os.path.exists(os.path.join(_ft, "config.json"))
            _retriever = Retriever(collection="bge_m3", model="BAAI/bge-m3", segment=False,
                                   expand=True, fp16=True, sem_expand=True, sem_K=3, sem_tau=0.45,
                                   use_rerank=_has_ft, rerank_model=_ft if _has_ft else None,
                                   n_candidates=30)
        elif _flag("USE_HYBRID"):
            from hybrid import HybridRetriever
            _retriever = HybridRetriever(use_rerank=use_rerank, expand=_flag("USE_QUERY_EXPAND"))
        else:
            _retriever = Retriever(use_rerank=use_rerank, expand=_flag("USE_QUERY_EXPAND"))
    return _retriever


def llm():
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


class ChatReq(BaseModel):
    question: str
    k: int = 5
    only_effective: bool = True   # chỉ lấy VB còn hiệu lực


@app.get("/health")
def health():
    try:
        return {"status": "ok", "vectors": retriever().count(),
                "llm_mode": os.environ.get("LLM_MODE", "mock"),
                "rerank": _flag("USE_RERANK"), "hybrid": _flag("USE_HYBRID"),
                "query_expand": _flag("USE_QUERY_EXPAND"), "bge": _flag("USE_BGE")}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/chat")
def chat(req: ChatReq):
    where = {"effect_status": "In effect"} if req.only_effective else None
    hits = retriever().search(req.question, k=req.k, where=where)
    context = format_context(hits)
    answer = llm().generate(req.question, context, hits=hits)
    sources = [{"document_number": h["metadata"].get("document_number"),
                "title": h["metadata"].get("title"),
                "legal_type": h["metadata"].get("legal_type"),
                "effect_status": h["metadata"].get("effect_status"),
                "score": round(h["score"], 3),
                "excerpt": h["text"][:250]} for h in hits]
    return {"answer": answer, "sources": sources}


@app.get("/", response_class=HTMLResponse)
def index():
    # Đọc từ đĩa mỗi lần -> sửa giao diện không cần restart server
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
    with open(path, encoding="utf-8") as f:
        return f.read()
