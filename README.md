# Hệ thống RAG tra cứu Văn bản Pháp luật / Y tế Việt Nam

Đồ án tốt nghiệp — chatbot hỏi-đáp dựa trên kiến trúc **RAG** (Retrieval-Augmented Generation).

## Kiến trúc

```
Câu hỏi
  │  tách từ (pyvi) + embedding (PhoBERT bi-encoder, 768d)
  ▼
ChromaDB  ──tìm top-k cosine + lọc hiệu lực──►  các chunk + metadata
  │
  ▼  build prompt (ngữ cảnh + yêu cầu trích dẫn)
LLM (PhoGPT-4B-Chat / mock)  ──►  câu trả lời + nguồn trích dẫn
```

## Thành phần

| File | Vai trò |
|------|---------|
| `build_chunks.py` | GĐ1: lọc VB y tế còn hiệu lực, làm sạch, chunk theo "Điều" → `legal_medical_chunks_clean.parquet` |
| `index_chroma.py` | GĐ2: embedding (PhoBERT) + nạp ChromaDB. Hỗ trợ `limit` + resume |
| `rag_core.py` | Lõi truy vấn (retrieval) |
| `llm.py` | Tầng sinh: `mock` (test) / `phogpt` (thật) |
| `app.py` | Backend FastAPI + phục vụ giao diện |
| `rerank.py` | Reranker cross-encoder (PhoRanker) — tùy chọn |
| `build_bm25.py` / `hybrid.py` | Chỉ mục BM25 + truy xuất hybrid (RRF + nhận diện số hiệu VB) |
| `static/index.html` | Giao diện **React** (SPA): lịch sử hội thoại (localStorage), thẻ nguồn, cài đặt |
| `static/vendor/` | React + ReactDOM + Babel tải sẵn local → **chạy offline**, không cần internet lúc demo |
| `eval/` | Bộ đánh giá: `golden_questions.json`, `evaluate.py`, `results.md` |

## Số liệu dữ liệu

- Nguồn: HF `th1nhng0/vietnamese-legal-documents` (518k VB pháp luật VN).
- Lọc ngành Y tế: 34,223 VB → còn hiệu lực ("In effect"): **21,490 VB**.
- Sau chunk theo Điều (~1040 ký tự) + khử trùng lặp: **367,462 chunk**.

## Cách chạy

```bash
# 1. (Đã chạy) Tạo dữ liệu chunk
python build_chunks.py

# 2. Tạo index. Index nhỏ để test:
python index_chroma.py 15000
#    Hoặc nạp TOÀN BỘ (chạy qua đêm ~13h trên CPU, resume nối tiếp được):
python index_chroma.py

# 2b. (tùy chọn, khuyến nghị) Xây chỉ mục BM25 cho hybrid search
python build_bm25.py           # tạo bm25_index/ + bm25_meta.pkl

# 3a. (1 lần) Cài llama-cpp-python bản prebuilt CPU + tải PhoGPT GGUF
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
python download_gguf.py        # tải models/PhoGPT-4B-Chat-Q4_K_M.gguf (2.36GB)

# 3b. Chạy web. Cấu hình tốt nhất = PhoGPT + hybrid + reranker (Windows PowerShell):
$env:LLM_MODE="gguf"; $env:USE_HYBRID="1"; $env:USE_RERANK="1"; uvicorn app:app --port 8000
#    Tối giản (vector thuần, mock LLM):  uvicorn app:app --port 8000
#    Hoặc chế độ test nhanh không cần LLM:  uvicorn app:app --port 8000  (LLM_MODE=mock mặc định)
# Mở http://localhost:8000

# 4. Đánh giá định lượng retrieval (cần index xong)
python eval/evaluate.py                # baseline (có tách từ)
python eval/evaluate.py --no-segment   # nhánh A/B: không tách từ
python eval/evaluate.py --rerank       # có reranker
# Xem kết quả tổng hợp ở eval/results.md
```

> ⏱️ Lần hỏi đầu mất ~90s nạp model (1 lần); các câu sau ~20–40s sinh trên CPU.
> LLM_MODE: `mock` (test, không cần model) · `gguf` (PhoGPT Q4_K_M qua llama.cpp, khuyến nghị) · `phogpt` (fp32 transformers, ~16GB RAM).

## Lý do thiết kế (cho báo cáo — kèm cách chứng minh)

| Quyết định | Lý do | Cách chứng minh |
|---|---|---|
| Chunk theo "Điều", ~1200 ký tự | Đơn vị ngữ nghĩa pháp luật; chunk 500 ký tự cắt giữa câu | Thí nghiệm A/B: recall@k với chunk 500 vs 1200 vs theo-Điều |
| Giữ số hiệu VB (`/ -`) | Định danh để trích dẫn & tra cứu chính xác | So sánh truy vấn hỏi theo số hiệu VB |
| Embedding bi-encoder PhoBERT | PhoBERT gốc là masked-LM, không tối ưu cho retrieval | So recall: bkai bi-encoder vs PhoBERT [CLS] thuần |
| Tách từ pyvi trước embedding | PhoBERT huấn luyện trên text đã tách từ | A/B: recall có vs không tách từ |
| Khử trùng lặp chunk | Boilerplate lặp làm nhiễu top-k | Đếm % chunk trùng bị loại (9,131) |
| Lọc `effect_status="In effect"` | Chatbot pháp luật chỉ nên tư vấn VB còn hiệu lực | Định tính: tránh trích dẫn VB hết hiệu lực |

## Hướng phát triển

- Reranker (cross-encoder) sau retrieval để tăng độ chính xác top-k.
- Hybrid search (BM25 + vector) cho truy vấn theo số hiệu/từ khóa.
- Đánh giá định lượng: bộ câu hỏi-đáp chuẩn, đo recall@k, MRR, faithfulness.
- Contextual chunking: thêm tiêu đề VB vào đầu mỗi chunk khi embedding.
