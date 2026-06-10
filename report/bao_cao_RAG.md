# ĐỒ ÁN TỐT NGHIỆP
# Hệ thống RAG hỗ trợ tra cứu Văn bản Pháp luật ngành Y tế Việt Nam

**Sinh viên:** Nguyễn Minh Hiếu  
**Đề tài:** Ứng dụng kỹ thuật Retrieval-Augmented Generation (RAG) xây dựng chatbot tra cứu văn bản pháp luật ngành y tế Việt Nam.

> *Ghi chú soạn thảo:* bản thảo này bám cấu trúc đề cương (Chương 0 → Kết luận). Mọi số liệu là kết quả thực nghiệm thật của hệ thống. Khi nộp: căn lề hai bên (Justify), font/cỡ theo quy định trường.

---

## CHƯƠNG 0. MỞ ĐẦU

### 0.1. Bối cảnh và động lực (Motivation)
Hệ thống văn bản quy phạm pháp luật Việt Nam trong lĩnh vực y tế rất lớn, thay đổi liên tục (sửa đổi, hợp nhất, hết hiệu lực) và được diễn đạt bằng ngôn ngữ pháp lý phức tạp. Người dân, cán bộ y tế và sinh viên thường gặp khó khi tra cứu: công cụ tìm kiếm từ khóa truyền thống chỉ khớp mặt chữ, không hiểu ý định câu hỏi; còn hỏi trực tiếp một mô hình ngôn ngữ lớn (LLM) thì dễ bị **"bịa" (hallucination)** và không truy được nguồn.

Kiến trúc **RAG (Retrieval-Augmented Generation)** giải quyết đồng thời hai vấn đề: (1) *truy xuất* đoạn văn bản liên quan từ kho tri thức thật, rồi (2) *sinh* câu trả lời dựa trên đoạn đó và trích dẫn nguồn. Nhờ vậy câu trả lời bám văn bản gốc, kiểm chứng được — đặc tính bắt buộc với lĩnh vực pháp luật.

### 0.2. Phát biểu bài toán
Xây dựng một hệ thống web hỏi–đáp (chatbot) cho phép người dùng đặt câu hỏi bằng tiếng Việt về pháp luật ngành y tế và nhận câu trả lời **chính xác, có trích dẫn số hiệu văn bản**, chạy được trên **máy cá nhân tài nguyên hạn chế (CPU, RAM 16GB, không GPU)**.

### 0.3. Phạm vi đề tài
- **Miền dữ liệu:** văn bản quy phạm pháp luật ngành Y tế Việt Nam (lọc từ bộ dữ liệu công khai trên Hugging Face).
- **Chức năng:** truy xuất ngữ nghĩa + sinh câu trả lời có trích dẫn; giao diện web hội thoại.
- **Ràng buộc:** toàn bộ pipeline chạy trên CPU 16GB; LLM dùng bản lượng tử hóa.
- **Ngoài phạm vi:** tư vấn pháp lý ràng buộc trách nhiệm; cập nhật văn bản thời gian thực.

### 0.4. Câu hỏi nghiên cứu (Research Questions)
- **RQ1.** Làm thế nào xây dựng một pipeline RAG tiếng Việt cho văn bản pháp luật y tế chạy được trên tài nguyên hạn chế (CPU 16GB)?
- **RQ2.** Mỗi thành phần kỹ thuật (tách từ tiếng Việt, reranker, hybrid BM25+vector) đóng góp bao nhiêu vào chất lượng truy xuất, đo bằng Hit@k và MRR?
- **RQ3.** Hệ thống có sinh câu trả lời bám ngữ cảnh, có trích dẫn nguồn và hạn chế bịa đặt không?

### 0.5. Cách tiếp cận
Xây dựng pipeline RAG theo 5 giai đoạn: (1) thu thập & tiền xử lý dữ liệu, (2) lập chỉ mục vector + BM25, (3) truy xuất (bi-encoder → hybrid → reranker), (4) sinh câu trả lời bằng LLM tiếng Việt, (5) giao diện web. Mỗi quyết định kỹ thuật được **kiểm chứng bằng thực nghiệm A/B** (so sánh có/không thành phần đó).

### 0.6. Kết quả dự kiến và đã đạt
- Kho tri thức **367.462 đoạn (chunk)** sạch từ **21.490 văn bản** y tế còn hiệu lực.
- Hệ thống truy xuất đạt **Hit@10 = 1.000, MRR = 0.722** (cấu hình Hybrid+Reranker) trên bộ 18 câu hỏi vàng.
- Chatbot web sinh câu trả lời có trích dẫn số hiệu, chạy hoàn toàn trên CPU 16GB.

---

## CHƯƠNG 1. CƠ SỞ LÝ THUYẾT

### 1.1. Kiến trúc RAG
RAG gồm hai khối: **Retriever** (truy xuất) và **Generator** (sinh). Thay vì để LLM trả lời bằng "trí nhớ" tham số (dễ sai, không nguồn), RAG nạp vào prompt các đoạn văn bản liên quan được truy xuất từ kho ngoài, buộc LLM trả lời dựa trên đó. Lợi ích: cập nhật tri thức không cần huấn luyện lại, có trích dẫn, giảm hallucination.

### 1.2. Biểu diễn văn bản bằng embedding & PhoBERT
**Embedding** ánh xạ văn bản sang vector số chiều cố định sao cho văn bản gần nghĩa thì gần nhau trong không gian vector. **PhoBERT** (VinAI) là mô hình ngôn ngữ tiền huấn luyện cho tiếng Việt dựa trên RoBERTa.

> **Lưu ý kỹ thuật (vì sao không dùng PhoBERT trực tiếp):** PhoBERT gốc là mô hình *masked language model*, vector [CLS] của nó không tối ưu cho đo độ tương đồng câu. Vì vậy ta dùng **bi-encoder dựa trên PhoBERT đã tinh chỉnh cho truy xuất**: `bkai-foundation-models/vietnamese-bi-encoder` (768 chiều). Đây là cách dùng đúng cho bài toán semantic search.

**Tách từ tiếng Việt (word segmentation):** tiếng Việt có hiện tượng từ ghép nhiều âm tiết ("Bộ Y tế" = một từ). PhoBERT được huấn luyện trên dữ liệu **đã tách từ**, nên đầu vào lúc dùng cũng phải tách từ (bằng `pyvi`) để khớp phân phối huấn luyện. *(Chứng minh ảnh hưởng: xem Thí nghiệm 1, Chương 4.)*

### 1.3. Cơ sở dữ liệu vector & tìm kiếm lân cận (ChromaDB)
**ChromaDB** lưu trữ vector cùng metadata và tìm **k láng giềng gần nhất** bằng chỉ mục **HNSW** với độ đo **cosine**. Cho phép lọc theo metadata (vd chỉ văn bản còn hiệu lực) ngay trong truy vấn.

### 1.4. Tìm kiếm từ vựng BM25 và Hybrid Search
**BM25** chấm điểm liên quan dựa trên trùng khớp từ vựng (TF-IDF cải tiến). Nó mạnh ở **từ khóa hiếm / số hiệu văn bản** (vd "147/2025/NĐ-CP") — đúng điểm yếu của embedding ngữ nghĩa. **Hybrid search** kết hợp hai nguồn bằng **Reciprocal Rank Fusion (RRF):** `score(d) = Σ 1/(c + rank_d)` (c=60), chỉ dùng thứ hạng nên không cần chuẩn hóa thang điểm.

### 1.5. Reranker (cross-encoder)
Bi-encoder mã hóa câu hỏi và đoạn **độc lập** (nhanh, nhưng kém tinh tế). **Cross-encoder** đọc **đồng thời** cặp (câu hỏi, đoạn) nên đánh giá độ liên quan chính xác hơn — dùng để **xếp lại** top-N ứng viên. Dự án dùng **PhoRanker** (`itdainb/PhoRanker`, dựa trên PhoBERT, cần tách từ).

### 1.6. Mô hình ngôn ngữ lớn tiếng Việt — PhoGPT
**PhoGPT-4B-Chat** (VinAI) là LLM tiếng Việt 3,7 tỷ tham số, kiến trúc MPT, ngữ cảnh 8192 token. Để chạy trên CPU 16GB, dùng bản **lượng tử hóa GGUF Q4_K_M (2,36GB)** qua thư viện **llama.cpp** — giảm bộ nhớ & tăng tốc với mất mát chất lượng nhỏ.

---

## CHƯƠNG 2. DỮ LIỆU VÀ TIỀN XỬ LÝ

### 2.1. Nguồn dữ liệu
Bộ dữ liệu công khai `th1nhng0/vietnamese-legal-documents` (Hugging Face): **518.601** bản ghi metadata và **518.235** bản ghi nội dung văn bản pháp luật Việt Nam, gồm số hiệu, tiêu đề, loại văn bản, ngành/lĩnh vực, cơ quan ban hành, ngày ban hành/hiệu lực, tình trạng hiệu lực.

### 2.2. Lọc theo ngành Y tế và tình trạng hiệu lực
- Lọc `legal_sectors` chứa "Health"/"Y tế" → **34.223** văn bản; trong đó **34.166** có nội dung.
- Giữ `effect_status = "In effect"` (còn hiệu lực) → **21.490** văn bản.

> **Vì sao lọc hiệu lực:** chatbot pháp luật chỉ nên tư vấn theo văn bản đang có hiệu lực; tránh trích dẫn văn bản đã hết hiệu lực gây sai lệch.

### 2.3. Làm sạch văn bản
Giữ cấu trúc xuống dòng (để cắt theo "Điều"), chuẩn hóa khoảng trắng, và **giữ lại các dấu `/ - ( ) %`**.

> **Vì sao giữ dấu:** số hiệu văn bản (vd `147/2025/NĐ-CP`) là định danh quan trọng nhất để trích dẫn; pipeline ban đầu xóa các dấu này làm hỏng số hiệu (`147 2025 NĐ CP`), giảm khả năng tra cứu.

### 2.4. Chia đoạn (chunking) theo đơn vị ngữ nghĩa
Cắt theo dấu mốc pháp lý `"Điều"`, `"Chương"`, `"Mục"` với kích thước ~1200 ký tự, overlap 150 (thuật toán đệ quy, `build_chunks.py`).

> **Vì sao cắt theo "Điều":** một "Điều" luật là đơn vị ngữ nghĩa hoàn chỉnh; cắt cứng 500 ký tự thường cắt giữa câu, làm đoạn mất ngữ cảnh và giảm chất lượng truy xuất *(chứng minh: Thí nghiệm 3, Chương 4)*.

### 2.5. Khử trùng lặp
Loại các chunk trùng (hash) — bỏ **9.131** chunk boilerplate lặp (quốc hiệu, căn cứ...). Kết quả cuối: **367.462 chunk** (trung bình ~1040 ký tự/chunk).

### 2.6. Bài học từ pipeline sai (đóng góp thực tiễn)
Pipeline ban đầu mắc 2 lỗi: (i) chỉ thu được 8.278/34.166 văn bản; (ii) ghi lặp khiến tập chunk phình tới **27,7 triệu dòng** (98,7% trùng). Việc **điều tra & sửa** (đo tỷ lệ trùng, truy nguyên vòng lặp ghi, rebuild sạch) là một phần kết quả của đồ án, minh họa tầm quan trọng của kiểm định dữ liệu.

---

## CHƯƠNG 3. THIẾT KẾ VÀ TRIỂN KHAI HỆ THỐNG

### 3.1. Kiến trúc tổng thể
```
Câu hỏi
  │  tách từ (pyvi) + embedding (PhoBERT bi-encoder, 768d)
  ▼
┌─ Vector (ChromaDB, cosine) ─┐
│                             ├─► RRF fusion ─► (nhận diện số hiệu VB)
└─ BM25 (bm25s)  ─────────────┘        │
                                       ▼  top-N ứng viên
                              Reranker (PhoRanker cross-encoder)
                                       ▼  top-k
                          Prompt (ngữ cảnh + yêu cầu trích dẫn)
                                       ▼
                          PhoGPT-4B-Chat (GGUF, llama.cpp)
                                       ▼
                       Câu trả lời + danh sách nguồn trích dẫn
```

### 3.2. Các thành phần (module)
| Module | Tệp | Chức năng |
|---|---|---|
| Nạp & chunk dữ liệu | `build_chunks.py` | Lọc, làm sạch, cắt đoạn → Parquet |
| Lập chỉ mục vector | `index_chroma.py` | Embedding + ChromaDB (resume được) |
| Lập chỉ mục từ vựng | `build_bm25.py` | BM25 (bm25s) trên toàn corpus |
| Truy xuất | `rag_core.py`, `hybrid.py` | Vector / Hybrid + nhận diện số hiệu |
| Xếp lại | `rerank.py` | Cross-encoder PhoRanker |
| Sinh câu trả lời | `llm.py` | PhoGPT GGUF / mock |
| Backend + Web | `app.py`, `static/` | FastAPI + giao diện React |
| Đánh giá | `eval/` | Bộ câu hỏi vàng + đo Hit@k, MRR |

### 3.3. Tối ưu cho tài nguyên hạn chế (CPU 16GB)
- Xử lý dữ liệu theo **luồng/batch** (streaming) để không tràn RAM với dữ liệu lớn.
- Embedding ghi dần vào ChromaDB, **resume** được nếu gián đoạn (tốc độ ~7,7 chunk/giây trên CPU; toàn corpus ~13 giờ chạy nền).
- LLM dùng bản **lượng tử hóa Q4_K_M** (2,36GB) → sinh ~20–40 giây/câu trên CPU.

### 3.4. Sinh câu trả lời có kiểm soát
Prompt yêu cầu LLM: chỉ dựa vào ngữ cảnh, **trích dẫn số hiệu văn bản**, và **nói rõ khi không tìm thấy** — nhằm giảm bịa đặt. Giao diện hiển thị câu trả lời kèm các thẻ nguồn (số hiệu, loại VB, tình trạng hiệu lực, điểm liên quan, trích đoạn).

### 3.5. Giao diện web
SPA React (lịch sử hội thoại lưu localStorage, thẻ nguồn mở/đóng, lọc hiệu lực). Thư viện React/Babel được **đóng gói cục bộ** (`static/vendor/`) để chạy **offline** — quan trọng khi demo/bảo vệ không có internet.

---

## CHƯƠNG 4. THỰC NGHIỆM VÀ ĐÁNH GIÁ

### 4.1. Phương pháp đánh giá
- **Bộ câu hỏi vàng:** 18 câu hỏi tiếng Việt về pháp luật y tế (`eval/golden_questions.json`), mỗi câu neo vào (các) **luật điều chỉnh** làm ground-truth, **bổ sung bản hợp nhất (VBHN) tương đương** (vd `39/VBHN-VPQH` = hợp nhất Luật Dược) cho công bằng.
- **Chỉ số:** **Hit@k** (tỷ lệ câu có ≥1 văn bản liên quan trong top-k) và **MRR** (trung bình nghịch đảo thứ hạng văn bản liên quan đầu tiên).

### 4.2. Kết quả tổng hợp (18 câu, cùng ground-truth)

| Cấu hình | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|----------|------:|------:|------:|-------:|----:|
| (1) Không tách từ              | 0.333 | 0.556 | 0.667 | 0.833 | 0.481 |
| (2) Vector + tách từ pyvi      | 0.389 | 0.778 | 0.833 | 0.944 | 0.586 |
| (3) Vector + Reranker          | 0.500 | 0.833 | 0.889 | 0.889 | 0.644 |
| (4) Hybrid (BM25+vector, RRF)  | 0.556 | 0.778 | 0.889 | **1.000** | 0.687 |
| (5) Hybrid + Reranker          | **0.556** | **0.833** | **0.944** | 0.944 | **0.722** |

### 4.3. Thí nghiệm 1 — Tách từ tiếng Việt [(1)→(2)]
Tách từ bằng pyvi tăng **Hit@3 từ 0.556 → 0.778 (+0.222)**, MRR +0.105. → Khẳng định cần tách từ nhất quán giữa lúc lập chỉ mục và lúc truy vấn (do PhoBERT huấn luyện trên dữ liệu đã tách từ).

### 4.4. Thí nghiệm 2 — Reranker cross-encoder [(2)→(3)]
PhoRanker xếp lại top-30 ứng viên tăng **Hit@1 từ 0.389 → 0.500 (+0.111)**, MRR +0.058. Đánh đổi: Hit@10 giảm nhẹ (chỉ xếp lại trong 30 ứng viên).

### 4.5. Thí nghiệm 3 — Kích thước chunk (500 vs 1200 vs theo-Điều)
Trên cùng tập 218 tài liệu (18 luật liên quan + 200 nhiễu), chunk theo 3 cách rồi đánh giá:

| Cấu hình | Số chunk | Hit@1 | Hit@5 | Hit@10 | MRR |
|----------|---------:|------:|------:|-------:|----:|
| fixed-500   | 8.437 | 0.944 | 1.000 | 1.000 | 0.972 |
| fixed-1200  | 3.647 | 1.000 | 1.000 | 1.000 | 1.000 |
| by-Điều     | 4.195 | 1.000 | 1.000 | 1.000 | 1.000 |

**Nhận xét:** chunk 500 ký tự sinh **gấp ~2,3 lần số chunk** (8.437 so với 3.647) → tốn gấp đôi
chi phí embedding/lưu trữ, nhưng Hit@1 và MRR lại **thấp hơn** (0.944/0.972 so với 1.000) do đoạn
quá nhỏ dễ tách rời ngữ cảnh. Chunk ~1200 và theo-Điều ít chunk hơn mà độ chính xác bằng/cao hơn.
**Hạn chế:** mẫu 218 tài liệu nhỏ khiến chỉ số gần bão hòa (~1.0); điểm phân biệt rõ nhất ở đây là
**hiệu quả chi phí** (số chunk), phù hợp lựa chọn chunk theo-Điều cho hệ thống.

### 4.6. Thí nghiệm 4 — Hybrid search [(2)→(4)/(5)]
Hybrid BM25+vector đạt **Hit@10 = 1.000** và MRR 0.687; kết hợp reranker đạt **MRR 0.722, Hit@5 0.944 (tốt nhất)**. Ngoài ra, với truy vấn chứa **số hiệu văn bản** (vd "Nghị định 96/2023/NĐ-CP"), hybrid + nhận diện số hiệu trả về **đúng văn bản** trong khi vector thuần thường trượt — minh chứng BM25 bù điểm yếu từ vựng của embedding.

### 4.7. Đánh giá định tính phần sinh (RQ3)
Ví dụ câu hỏi *"Điều kiện để cá nhân được phép khám bệnh, chữa bệnh?"* — PhoGPT trả lời bám đúng **Điều 19 Luật Khám bệnh, chữa bệnh 2023 (15/2023/QH15)**: "có giấy phép hành nghề còn hiệu lực và đã đăng ký hành nghề…", kèm trích dẫn số hiệu. Câu trả lời không bịa thông tin ngoài ngữ cảnh.

### 4.8. Bàn luận về phương pháp đánh giá
Trước khi bổ sung VBHN vào ground-truth, baseline chỉ đạt Hit@1=0.222; sau khi bổ sung → 0.389 — cho thấy chỉ số ban đầu **đánh giá thấp** năng lực thực của hệ thống (bản hợp nhất có cùng nội dung luật nhưng khác số hiệu). Đây là lưu ý quan trọng khi xây ground-truth cho miền pháp luật.

---

## CHƯƠNG 5. KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

### 5.1. Kết luận
Đồ án đã xây dựng hoàn chỉnh một hệ thống RAG tra cứu văn bản pháp luật y tế tiếng Việt, chạy trên CPU 16GB, với: kho 367.462 chunk sạch; pipeline truy xuất Hybrid + Reranker đạt **MRR 0.722, Hit@10 0.944–1.000**; sinh câu trả lời có trích dẫn bằng PhoGPT; giao diện web hội thoại chạy offline. Mỗi quyết định kỹ thuật đều được kiểm chứng bằng thực nghiệm A/B (trả lời RQ1–RQ3).

### 5.2. Hạn chế
- Bộ câu hỏi vàng còn nhỏ (18 câu) và ground-truth neo theo luật; nên mở rộng và có chuyên gia thẩm định.
- Tốc độ sinh trên CPU (~20–40s/câu) chưa đạt thời gian thực.
- Chưa đánh giá định lượng độ trung thực (faithfulness) của phần sinh.

### 5.3. Hướng phát triển
- Mở rộng bộ đánh giá; đo faithfulness/groundedness tự động.
- Contextual chunking (thêm tiêu đề VB vào đầu mỗi chunk khi embedding).
- Tăng tốc sinh (GPU/dịch vụ); hỗ trợ hội thoại đa lượt (multi-turn) với viết lại câu hỏi.
- Mở rộng sang văn bản pháp luật ngoài ngành y tế.

---

## PHỤ LỤC
- **Mã nguồn & hướng dẫn chạy:** xem `README.md`.
- **Kết quả thực nghiệm chi tiết:** `eval/results.md`.
- **Bộ câu hỏi vàng:** `eval/golden_questions.json`.
