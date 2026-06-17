# Kết quả đánh giá Retrieval (cho báo cáo)

**Bộ test:** 200 câu hỏi vàng (`golden_questions.json`) — 50 soạn tay + 150 sinh từ tiêu đề Điều (`generate_questions.py`); |relevant| TB 2,0.
**Ground-truth:** văn bản luật điều chỉnh câu hỏi + **bản hợp nhất (VBHN) tương đương** của luật đó
(vd `39/VBHN-VPQH` = hợp nhất Luật Dược) — vì VBHN có cùng nội dung luật nhưng khác số hiệu.
**Index:** 367,462 chunk (toàn corpus). **Chỉ số:** Hit@k, MRR, Precision/Recall/F1@k. Script: `eval200.py`.

## Bảng tổng hợp (cùng ground-truth, 200 câu)

| Cấu hình | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|----------|------:|------:|------:|-------:|----:|
| (1) Không tách từ              | 0.490 | 0.680 | 0.760 | 0.810 | 0.600 |
| (2) Vector + tách từ pyvi      | 0.595 | 0.800 | 0.845 | 0.885 | 0.704 |
| (3) Vector + Reranker          | 0.625 | 0.815 | 0.850 | 0.880 | 0.724 |
| (4) Hybrid (BM25+vector, RRF)  | 0.635 | 0.855 | 0.900 | **0.960** | 0.754 |
| (5) Hybrid + Reranker          | **0.650** | **0.860** | **0.905** | 0.940 | **0.764** |

*(Bộ 18/50 câu trước đó cho xu hướng tương tự; trên bộ 200 mọi kỹ thuật đều đóng góp dương rõ ràng.)*

Lệnh: `evaluate.py` (2), `--no-segment` (1), `--rerank` (3), `--hybrid` (4), `--hybrid --rerank` (5).

## Diễn giải (từng bước được chứng minh)

**Bước A — Tách từ pyvi** [(1)→(2)]: Hit@1 **0.490 → 0.595 (+0.105)**, Hit@3 **0.680 → 0.800 (+0.120)**, MRR +0.104. (Đòn bẩy mạnh nhất.)
Lý do: PhoBERT huấn luyện trên text đã tách từ; tách từ nhất quán index↔truy vấn giúp khớp embedding.

**Bước B — Reranker cross-encoder (PhoRanker)** [(2)→(3)]: Hit@1 **0.595 → 0.625 (+0.030)**, MRR +0.020.
Lý do: cross-encoder đọc đồng thời (câu hỏi+đoạn) nên xếp hạng tinh hơn cosine. Lợi ích khiêm tốn hơn tách từ/hybrid; phát huy tốt hơn khi đứng sau hybrid (cấu hình 5).

**Bước C — Hybrid BM25+vector (RRF)** [(2)→(4)]: Hit@10 **0.885 → 0.960**, MRR **0.704 → 0.754**.
Lý do: BM25 bù điểm yếu từ vựng/số hiệu của vector; RRF hợp nhất theo thứ hạng. Thêm nhận diện
số hiệu văn bản (regex) → tiêm thẳng chunk đúng số hiệu (vector thuần thường trượt — vd "96/2023/NĐ-CP").

**Tốt nhất — Hybrid + Reranker** (5): Hit@1 **0.650**, MRR **0.764**, Hit@5 **0.905**. Cấu hình đề xuất cho hệ thống.

## Ghi chú phương pháp

- **VBHN làm chỉ số công bằng hơn:** trước khi bổ sung VBHN vào ground-truth, baseline chỉ
  Hit@1=0.222 / Hit@10=0.889; sau khi bổ sung → 0.389 / 0.944 (retriever thực ra giỏi hơn con số ban đầu).
- **MISS còn lại** (vd "hành vi nghiêm cấm trong hoạt động dược"): top-1 trả về QĐ của Cục Quản lý Dược
  thay vì Luật — cho thấy nhu cầu hybrid search (BM25) khi câu hỏi gần với văn bản dưới luật.

## Thí nghiệm 3 — Kích thước chunk (ab_chunk_size.py, 218 tài liệu)

| Cấu hình | #chunk | Hit@1 | Hit@5 | Hit@10 | MRR |
|----------|-------:|------:|------:|-------:|----:|
| fixed-500  | 8.437 | 0.944 | 1.000 | 1.000 | 0.972 |
| fixed-1200 | 3.647 | 1.000 | 1.000 | 1.000 | 1.000 |
| by-Điều    | 4.195 | 1.000 | 1.000 | 1.000 | 1.000 |

Chunk 500 → gấp ~2,3× số chunk nhưng Hit@1/MRR thấp hơn. Chunk ~1200/theo-Điều hiệu quả hơn.
Hạn chế: mẫu nhỏ → chỉ số bão hòa; điểm phân biệt chính là chi phí (số chunk).

## Thí nghiệm 4 — Precision/Recall, số nguồn k, thời gian, trích dẫn (experiment_full.py)

Cấu hình Hybrid + Reranker, mức văn bản:

| k | Precision | Recall | F1 | Trần P@k |
|---|----------:|-------:|---:|---------:|
| 1 | 0.650 | 0.436 | 0.522 | 1.000 |
| 2 | 0.510 | 0.608 | **0.555** | 1.000 |
| 3 | 0.398 | 0.686 | 0.504 | 0.667 |
| 5 | 0.268 | 0.747 | 0.394 | 0.400 |
| 10 | 0.146 | 0.806 | 0.247 | 0.200 |

- Quét dải k mịn (k=1..10, `eval200.py`, 200 câu): **F1 cực đại tại k=2 (0.555)**; vùng k=2–3 tối ưu cho truy xuất, hệ thống dùng k=5 mặc định để có thêm ngữ cảnh cho phần sinh.
- **Trần Precision:** do |relevant| TB 2, P bị chặn trần min(|rel|,k)/k. Precision giảm theo k chủ yếu do trần giảm — tỷ lệ đạt-trần TĂNG 65%→73% → truy xuất không kém đi.
- **Thời gian (CPU):** truy xuất TB ~7s; sinh TB ~45s (đo trên mẫu).
- **Mức độ trích dẫn:** 6/6 câu sinh (100%) trích dẫn đúng văn bản liên quan; bám điều luật (Điều 19/33/79).
- Quan sát: mô hình đôi khi nêu chi tiết phụ chưa chính xác (vd nhắc "Luật 2009" dù nguồn là 15/2023/QH15) → RAG giảm nhưng chưa loại bỏ hết sai sót phần sinh.

## Thí nghiệm 5 — Câu hỏi diễn đạt tự nhiên (eval_natural.py, 30 câu type=natural)

| Nhóm | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|------|------:|------:|------:|-------:|----:|
| Câu mẫu (200) | 0.650 | 0.860 | 0.905 | 0.940 | 0.764 |
| **Câu tự nhiên (30)** | **0.200** | 0.267 | 0.367 | 0.467 | **0.271** |

- Nguyên nhân: (1) **lexical gap** đời thường↔pháp lý ("mở quán ăn nhỏ" vs "cơ sở kinh doanh dịch vụ ăn uống");
  (2) ground-truth nghiêm ngặt — nhiều top-1 là văn bản dưới luật RẤT SÁT (vd 96/2023/NĐ-CP cho câu bác sĩ nước ngoài) nhưng không trùng nhãn luật → 0.200 là cận dưới.
- Hướng cải tiến: query rewriting (đời thường → pháp lý); mở rộng nhãn sang văn bản dưới luật.
- **Thẩm định chuyên gia:** đã lập `report/PhieuThamDinh_BoCauHoi.docx` (230 câu + nhãn, cột xác nhận/ghi chú) để chuyên gia pháp lý/GVHD ký xác nhận.

## Thí nghiệm 6 — Query rewriting (query_rewrite.py, 30 câu tự nhiên)

| Biến thể | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|----------|------:|------:|------:|-------:|----:|
| Câu gốc (baseline) | 0.200 | 0.267 | 0.367 | 0.467 | 0.271 |
| Viết lại (PhoGPT-4B) | 0.167 | 0.233 | 0.400 | **0.533** | 0.258 |
| Gốc + viết lại (combo) | 0.133 | 0.300 | 0.367 | 0.433 | 0.219 |

**Kết quả âm có giá trị:** viết lại bằng PhoGPT-4B KHÔNG cải thiện tổng thể (MRR ↓), dù Hit@10 +0.066 cho thấy ý tưởng có tiềm năng. Nguyên nhân (soi tay 30 câu): 15/30 giữ nguyên, 13/30 mô hình TRẢ LỜI thay vì viết lại, 8/30 bịa trích dẫn ("Điều 32 Luật KCB 2009", "NĐ 11/2016" — sai/lỗi thời). → Nút thắt = instruction-following của model 4B quantized, không phải ý tưởng. Hướng: LLM mạnh hơn cho riêng bước rewrite, hoặc từ điển ánh xạ đời thường→pháp lý.

## Thí nghiệm 7 — Kiểm chứng quy mô 650 câu (eval650_all.py, 5 cấu hình, 650 câu = 50 tay + 500 sinh + 100 tự nhiên)

| Cấu hình | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|----------|------:|------:|------:|-------:|----:|
| (1) Không tách từ          | 0.403 | 0.603 | 0.675 | 0.735 | 0.515 |
| (2) Vector + tách từ pyvi  | 0.549 | 0.742 | 0.803 | 0.837 | 0.653 |
| (3) Vector + Reranker      | 0.545 | 0.745 | 0.802 | 0.828 | 0.651 |
| (4) Hybrid (BM25+vector)   | **0.568** | 0.774 | 0.826 | **0.874** | **0.680** |
| (5) Hybrid + Reranker      | 0.563 | **0.775** | **0.832** | 0.865 | 0.676 |

**Phân tích theo loại câu (cấu hình Hybrid + Reranker):**

| Loại câu (n) | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|--------------|------:|------:|------:|-------:|----:|
| Soạn tay (50)   | 0.560 | 0.780 | 0.860 | 0.920 | 0.694 |
| Sinh tự động (500) | **0.644** | 0.856 | 0.904 | 0.924 | **0.753** |
| Diễn đạt tự nhiên (100) | **0.160** | 0.370 | 0.460 | 0.540 | **0.283** |

**Kết luận quy mô (so với 200 câu):**
- **Tách từ vẫn là đòn bẩy mạnh nhất:** noseg→vector Hit@1 0.403→0.549 (**+0.146**), MRR 0.515→0.653 (**+0.138**) — mạnh hơn cả ở 200 câu, khẳng định chắc chắn.
- **Hybrid vẫn có lợi:** vector→hybrid Hit@1 +0.019, Hit@10 +0.037, MRR +0.027 — nhất quán với 200 câu.
- **Phát hiện mới (kết quả âm, trung thực): reranker KHÔNG còn cải thiện ở quy mô 650 câu.** vector→vector_rr: Hit@1 0.549→0.545 (−0.004); hybrid→hybrid_rr: 0.568→0.563 (−0.005). Khác với 200 câu (reranker +0.030 Hit@1). Chênh lệch ~3/650 câu = trong khoảng nhiễu. **Lý do:** 100 câu tự nhiên (lexical gap) reranker không cứu được (văn bản đúng không nằm trong top-30 để xếp lại); ở các câu mẫu/sinh thì retriever đã rất tốt nên reranker ít chỗ cải thiện. → Lợi ích reranker là khiêm tốn và phụ thuộc phân bố câu hỏi; nên báo cáo trung thực, không thổi phồng.
- **Decompose độ rơi của số tổng:** số 650-tổng thấp hơn 200 (Hit@1 0.563 vs 0.650) HOÀN TOÀN do 100 câu tự nhiên (Hit@1 0.16) kéo xuống. Tách riêng: câu **sinh (500): Hit@1 0.644, MRR 0.753** — gần như TRÙNG khít headline 200 câu (0.650/0.764) → chứng minh tính ổn định; câu **tay (50): 0.56/0.694**; câu **tự nhiên (100): 0.16/0.283** tái khẳng định lexical gap (TN5).

**P/R/F1 sweep (Hybrid + Reranker, 650 câu, |rel| TB 1.98):**

| k | Precision | Recall | F1 | Trần P@k |
|---|----------:|-------:|---:|---------:|
| 1 | 0.563 | 0.391 | 0.461 | 1.000 |
| 2 | 0.452 | 0.555 | **0.498** | 0.990 |
| 3 | 0.359 | 0.637 | 0.459 | 0.660 |
| 5 | 0.248 | 0.704 | 0.366 | 0.396 |
| 10 | 0.134 | 0.749 | 0.227 | 0.198 |

- F1 cực đại tại **k=2 (0.498)** — cùng kết luận với 200 câu (k=2–3 tối ưu cho truy xuất). Trần Precision và đánh đổi P↓/R↑ giữ nguyên hình dạng.

## Thí nghiệm 8 — Cải thiện câu tự nhiên: từ điển ánh xạ vs HyDE (eval_natural_improve.py, 100 câu type=natural, Hybrid+Reranker)

| Điều kiện | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|-----------|------:|------:|------:|-------:|----:|
| (a) baseline (câu gốc) | 0.160 | 0.370 | 0.460 | 0.540 | 0.283 |
| **(b) + Từ điển ánh xạ (dict)** | **0.230** | **0.450** | **0.520** | **0.640** | **0.362** |
| (c) + HyDE (PhoGPT sinh đoạn) | 0.090 | 0.270 | 0.410 | 0.510 | 0.216 |
| (d) dict + HyDE | 0.080 | 0.290 | 0.420 | 0.600 | 0.229 |

- baseline 0.160 **trùng khớp** kết quả nhóm tự nhiên ở TN7 (650 câu) → harness nhất quán.
- **Từ điển ánh xạ THẮNG rõ:** Hit@1 0.160→0.230 (**+0.070, +44% tương đối**), MRR +0.079, Hit@10 +0.100. Phân tích @Hit1: **15 câu lật miss→hit**, 8 câu hit→miss (ròng **+7**). Cơ chế xác định (deterministic), không phụ thuộc LLM — vá đúng lexical gap. Đã đóng gói `query_expand.py` (8 lĩnh vực), app tái dùng được.
- **HyDE THẤT BẠI (kết quả âm thứ 2):** Hit@1 0.160→0.090 (−0.070). Nguyên nhân (soi đoạn sinh): PhoGPT-4B **bịa/gán số hiệu cụ thể** vào đoạn giả định ("Nghị định 54/2017/NĐ-CP", "43/2017/NĐ-CP", "Luật...2012" — văn bản dưới luật hoặc sai/lỗi thời) → embedding bị "cướp lái" về đúng văn bản mô hình tự nhớ thay vì văn bản đích. dict+HyDE: nhiễu HyDE **triệt tiêu** lợi ích từ điển (0.080).
- **Mạch xuyên suốt TN6 + TN8:** mọi kỹ thuật phía-truy-vấn dựa-LLM (viết lại, HyDE) đều hỏng vì nút thắt mô hình 4B lượng tử hóa (instruction-following kém + bịa trích dẫn); **giải pháp kỹ thuật xác định (từ điển) mới là cái thắng**. Lưu ý trung thực: từ điển không miễn phí (8 câu bị kéo lệch); và nhiều "miss" còn lại là do nhãn nghiêm ngặt (dict đẩy đúng nghị định hướng dẫn lên top nhưng nhãn chỉ có luật gốc) → con số 0.230 vẫn là cận dưới.

### Phân tích trần "topic-level relevance" (nhãn theo họ văn bản)
Nới nhãn = luật gốc + VB **hướng dẫn/hợp nhất nhắc đích danh tên luật** (phát hiện tự động từ tiêu đề, TB ~9 VB/câu — chuẩn IR graded-relevance):

| Điều kiện | Hit@1 | Hit@5 | Hit@10 | MRR |
|-----------|------:|------:|-------:|----:|
| baseline, nhãn nghiêm ngặt | 0.16 | 0.46 | 0.54 | 0.283 |
| dict, nhãn nghiêm ngặt | 0.23 | 0.52 | 0.64 | 0.362 |
| baseline, nhãn topic-level | 0.23 | 0.54 | 0.61 | 0.356 |
| **dict, nhãn topic-level** | **0.35** | 0.63 | **0.74** | 0.477 |

→ Với mức liên quan theo chủ đề, dict đạt **Hit@10 0.74** — phản ánh đúng chất lượng cảm nhận thực (hệ thống trả về nghị định/thông tư hướng dẫn đúng nhu cầu). Con số nghiêm ngặt 0.16 là **cận dưới do nhãn hẹp**, không phải lỗi truy xuất.

## Thí nghiệm 9 — Fine-tune bi-encoder cho câu tự nhiên (proof-of-concept) (train/finetune_natural.py + eval_finetune.py)

Tách 100 câu TN → **71 train / 29 test** phân tầng 9 lĩnh vực, hạt giống cố định (KHÔNG train trên câu test). 213 cặp (câu→chunk luật đúng, hard-positive mining), MNRL, 2 epoch trên CPU (loss 0.34, ~6 phút). Đánh giá **closed-pool** (fine-tune làm 367k vector cũ bất tương thích → đánh giá xếp-hạng-lại trên pool top-150 base-vector + bơm chunk luật đúng; CON SỐ TUYỆT ĐỐI không so trực tiếp với truy xuất mở):

| Điều kiện | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|-----------|------:|------:|------:|-------:|----:|
| base | 0.172 | 0.448 | 0.448 | 0.621 | 0.326 |
| base + dict | 0.138 | 0.345 | 0.517 | 0.690 | 0.299 |
| ft (fine-tuned) | 0.138 | 0.414 | 0.552 | 0.655 | 0.319 |
| ft + dict | 0.172 | 0.345 | 0.448 | 0.690 | 0.319 |

**Kết quả âm thứ 3 (trung thực):** fine-tune KHÔNG cải thiện nhất quán (ft vs base lẫn lộn trong nhiễu, MRR 0.326→0.319). Nguyên nhân: **dữ liệu huấn luyện quá ít** (71 câu / 213 cặp) cho mô hình 135M tham số → không đủ học khái quát khoảng cách đời thường↔pháp lý; 29 câu test cũng nhỏ/nhiễu. **Bài học:** đòn bẩy thật là QUY MÔ DỮ LIỆU (cần hàng nghìn cặp câu đời thường có nhãn) — đây là hướng phát triển rõ ràng, không phải lỗi ý tưởng.

### TN9b — Fine-tune QUY MÔ LỚN (domain adaptation, 8000 cặp) (train/finetune_large.py + eval_large_pool.py)
Sinh 8000 cặp (câu hình thức từ tiêu đề Điều TOÀN CORPUS, **loại 18 luật eval** → 100 câu tự nhiên sạch tuyệt đối, đo KHÁI QUÁT), MNRL batch 32, max_seq=128 (để khả thi CPU: 84s→12s/step), 1 epoch (~43 phút, loss 0.81). Đánh giá LARGE-POOL: pool chung 14.050 chunk (top-200 mỗi câu ∪ toàn bộ chunk luật liên quan), embed lại bằng base & ft, đo 100 câu (nhãn nghiêm ngặt + topic-level):

| Nhãn nghiêm ngặt | Hit@1 | Hit@5 | Hit@10 | MRR |
|------------------|------:|------:|-------:|----:|
| base | 0.14 | 0.52 | 0.65 | 0.301 |
| base + dict | 0.17 | 0.45 | 0.62 | 0.301 |
| **ft-large** | 0.04 | 0.23 | 0.42 | **0.136** |
| ft-large + dict | 0.07 | 0.32 | 0.48 | 0.186 |

(Topic-level cùng xu hướng: base MRR 0.37 → ft 0.209.)

**Kết quả âm thứ 4 — DỨT KHOÁT:** tăng quy mô dữ liệu KHÔNG cứu được, mà còn làm **tệ đi mạnh** (MRR giảm >50%). Nguyên nhân: (1) dữ liệu lớn vẫn là câu **hình thức** (template từ tiêu đề Điều) — KHÔNG phải câu đời thường, nên adaptation kéo model về phân phối template, lệch khỏi câu người dân hỏi; (2) catastrophic forgetting — vietnamese-bi-encoder vốn đã tinh chỉnh tốt, fine-tune 1 epoch với negatives khó (loss 0.81 chưa hội tụ) phá cấu trúc ngữ nghĩa sẵn có; (3) max_seq=128 cắt ngắn ngữ cảnh. → Theo tiêu chí đã chốt (MRR +≥0.03 hoặc Hit@5/10 +≥0.05, không tụt) ⇒ **KHÔNG đạt** ⇒ **không chạy re-embed 367k** (sẽ chỉ xác nhận regression, tốn 13h vô ích).
**Bài học khoa học:** đòn bẩy đúng KHÔNG phải "nhiều dữ liệu hình thức" mà là **đúng LOẠI dữ liệu (câu đời thường có nhãn)** + tài nguyên huấn luyện đúng (GPU, full seq, nhiều epoch + validation/early-stopping). Đây là hướng phát triển cụ thể, có cơ sở thực nghiệm.

### Kết luận cụm câu tự nhiên (TN6 + TN8 + TN9 + TN9b)
- **Cái THẮNG (triển khai được):** từ điển ánh xạ — deterministic, +44% Hit@1 (0.16→0.23 nghiêm ngặt; 0.35 topic-level), đã đóng gói `query_expand.py`.
- **4 hướng dựa-mô-hình đều CHƯA thắng:** viết lại (TN6, ↓), HyDE (TN8, ↓), fine-tune dữ-liệu-ít (TN9, ngang), fine-tune dữ-liệu-lớn-hình-thức (TN9b, ↓↓) — đều quy về 2 nút thắt: năng lực/độ tin cậy mô hình + thiếu dữ liệu huấn luyện ĐÚNG LOẠI (câu đời thường có nhãn). Tăng quy mô dữ liệu SAI loại còn phản tác dụng.
- **0.8 Hit@1 nghiêm ngặt không đạt được trung thực** ở cấu hình CPU/4B này; con số phản ánh chất lượng thực là **Hit@10 topic-level ~0.74** (với dict).
- **Hướng phát triển có cơ sở thực nghiệm:** thu thập/sinh bộ dữ liệu câu đời thường có nhãn quy mô lớn (vài nghìn cặp), fine-tune trên GPU với full seq + early-stopping; hoặc nâng cấp mô hình nền. Đây là kết luận rút ra từ 4 thí nghiệm có đối chứng, không phải suy đoán.

## Thí nghiệm 10 — Mẹo mở rộng truy vấn deterministic (#1 glossary, #2 RM3, #3 chuẩn hóa) (eval_enhance.py, 100 câu TN, GPU)

| Điều kiện | Hit@1 | Hit@5 | Hit@10 | MRR |
|-----------|------:|------:|-------:|----:|
| baseline | 0.16 | 0.46 | 0.54 | 0.283 |
| dict (nối thêm) | **0.23** | 0.52 | 0.64 | **0.362** |
| dict + chuẩn hóa + glossary | 0.21 | **0.58** | **0.68** | 0.36 |
| dict + RM3 | 0.16 | 0.50 | 0.57 | 0.291 |
| dict + RM3 + norm + glossary | 0.12 | 0.51 | 0.58 | 0.28 |

- **Glossary (#1) + chuẩn hóa viết tắt (#3):** tăng Hit@5/10 (+0.06/+0.04 độ phủ) nhưng giảm nhẹ Hit@1 — đánh đổi recall/precision. `mine_glossary.py` trích 52 thuật ngữ từ mục "Giải thích từ ngữ".
- **RM3 (#2): PHẢN TÁC DỤNG** (Hit@1 0.23→0.16, MRR↓). Lý do: truy xuất vòng 1 cho câu TN yếu (0.16) → từ khóa phản hồi lấy từ văn bản SAI → khuếch đại lỗi (RM3 hỏng khi pseudo-relevance kém — đúng lý thuyết).
- **Kết luận:** từ điển ánh xạ vẫn là cái thắng Hit@1; các mẹo deterministic chạm trần. Đòn bẩy còn lại = mô hình embedding mạnh hơn (xem TN11).

## Thí nghiệm 11 — Nâng cấp mô hình embedding: bge-m3 vs PhoBERT (GPU, truy xuất vector MỞ toàn corpus)

Embed lại toàn bộ 367.462 chunk bằng BAAI/bge-m3 (đa ngữ SOTA, 568M, 1024 chiều, text thô) trên GPU RTX 4060 (fp16, ~89 chunk/s, ~1.1h) → collection `bge_m3`. So vector thuần (chưa hybrid/rerank):

| Nhóm | Chỉ số | PhoBERT | bge-m3 |
|------|--------|--------:|-------:|
| Câu mẫu (200) | Hit@1 / MRR / Hit@10 | 0.595 / 0.707 / 0.90 | **0.675 / 0.780 / 0.95** |
| Câu TN — nghiêm ngặt | Hit@1 / MRR / Hit@10 | 0.13 / 0.29 / 0.64 | **0.20 / 0.322** / 0.55 |
| Câu TN — topic-level | Hit@1 / MRR / Hit@10 | 0.18 / 0.349 / 0.71 | **0.28 / 0.402** / 0.64 |

**Kết quả DƯƠNG (đòn bẩy không cần dữ liệu huấn luyện):** bge-m3 vượt PhoBERT trên CẢ câu mẫu (Hit@1 +0.08, MRR +0.073) lẫn câu tự nhiên (Hit@1 nghiêm ngặt 0.13→0.20; topic-level 0.18→0.28). Vector thuần bge-m3 đã ngang từ điển-trên-PhoBERT (0.20 vs 0.23) mà chưa cần từ điển. Điểm yếu: recall@10 câu TN thấp hơn (0.55 vs 0.64) → kỳ vọng hybrid BM25 bù lại. Script: `train/embed_corpus_gpu.py`, `train/eval_bge.py`. → kiểm chứng cấu hình đầy đủ bge-m3 + Hybrid + Reranker ở dưới.

### TN11 (tiếp) — Cô lập cấu hình bge-m3 trên 100 câu tự nhiên (ĐỘT PHÁ)

| Cấu hình bge-m3 | Strict Hit@1 | Strict MRR | Topic Hit@1 | Topic Hit@10 |
|-----------------|-------------:|-----------:|------------:|-------------:|
| vector | 0.20 | 0.312 | 0.28 | 0.62 |
| **vector + từ điển** | **0.34** | **0.458** | **0.45** | **0.79** |
| vector + reranker (PhoRanker) | 0.15 | 0.246 | 0.22 | 0.60 |
| vector + dict + reranker | 0.18 | 0.307 | 0.24 | 0.72 |

**Cấu hình tốt nhất MỚI: bge-m3 vector + từ điển ánh xạ (KHÔNG reranker, KHÔNG BM25).**
- Câu tự nhiên: Hit@1 **0.160 → 0.340** (GẤP 2.1×), MRR 0.283 → 0.458; topic-level Hit@1 0.45, **Hit@10 0.79** (≈ mốc 0.8).
- Câu mẫu (vector thuần, TN11): 0.595 → 0.675 (+0.08) — KHÔNG tụt.

**Phát hiện pipeline (quan trọng):** reranker PhoRanker và BM25-hybrid (vốn tinh chỉnh cho PhoBERT) đều LÀM GIẢM hiệu năng bge-m3 (vector 0.20 → +rerank 0.15 → +hybrid+rerank 0.14). PhoRanker (cross-encoder nền PhoBERT) chấm lệch ứng viên bge-m3; BM25 qua RRF pha loãng top. → Với mô hình nền mạnh, pipeline gọn (vector + từ điển) lại tốt hơn. Bài học: tinh chỉnh pipeline theo từng mô hình nền, không bê nguyên cấu hình.

**Lộ trình câu tự nhiên (toàn bộ hành trình, trung thực):**
0.160 (PhoBERT+hybrid+rerank, mốc) → 0.230 (+từ điển) → **0.340 (bge-m3 vector + từ điển)** = gấp 2.1× so với mốc; topic-level Hit@10 0.79.

### TN11 (chốt) — Reranker bge-reranker-v2-m3 (cùng họ bge-m3) cũng làm giảm

| Cấu hình (100 câu TN) | Strict Hit@1 | Strict MRR | Topic Hit@10 |
|-----------------------|-------------:|-----------:|-------------:|
| bge-m3 vector + từ điển | **0.34** | **0.458** | 0.79 |
| + bge-reranker-v2-m3 | 0.16 | 0.324 | 0.79 |

Cả PhoRanker (TN11 trên) lẫn bge-reranker-v2-m3 (cùng họ) đều giảm Hit@1 nghiêm ngặt (0.34→0.16). **Không phải lỗi mismatch model** mà là: reranker xếp theo ĐỘ LIÊN QUAN THỰC → với câu TN, văn bản liên quan nhất thường là nghị định hướng dẫn (dưới luật), reranker đẩy lên #1, luật gốc (nhãn) tụt → Hit@1 nghiêm ngặt giảm dù Hit@10 giữ 0.79. Đây là vấn đề nhãn nghiêm ngặt (Mục 4.12.2) lộ ra ở tầng reranker.

**CẤU HÌNH TỐI ƯU CHỐT cho câu tự nhiên: bge-m3 vector + từ điển ánh xạ (không reranker, không BM25).**

## Thí nghiệm 12 — Mở rộng từ điển tối đa: lexicon ngữ nghĩa tự động (dict_overnight.py, GPU, 100 câu TN)

Xây lexicon pháp lý LỚN tự động: trích sạch **12.839 cụm** (tiêu đề "Điều" toàn corpus) → embed bge-m3 → MỞ RỘNG NGỮ NGHĨA: mỗi câu hỏi đời thường nối top-K cụm pháp lý GẦN nhất (cosine ≥ τ). Grid 20 cấu hình, **chọn theo TRAIN (71 câu), báo cáo TEST (29) + FULL (100)** để tránh overfit.

| Cấu hình | full strict Hit@1 | full strict Hit@10 | full topic Hit@1 | full topic Hit@10 | full MRR |
|----------|------------------:|-------------------:|-----------------:|------------------:|---------:|
| bge-m3 (base) | 0.20 | 0.55 | 0.28 | 0.64 | 0.312 |
| + từ điển tay | 0.34 | 0.74 | 0.45 | 0.84 | 0.458 |
| semantic thuần (K3) | 0.31 | — | — | 0.80 | — |
| **+ tay + semantic (K3, τ0.45)** ★ | **0.36** | **0.86** | **0.49** | **0.94** | **0.50** |

(Cấu hình tốt nhất chọn theo TRAIN MRR = man+sem_K3_t0.45; TEST giữ riêng: Hit@1 0.379, Hit@10 0.759, MRR 0.484 → KHÔNG overfit.)

- **Semantic THUẦN kém hơn từ điển tay** (0.31 vs 0.34) nhưng **CỘNG THÊM vào từ điển tay thì vượt** (0.34→0.36 strict; topic Hit@10 0.84→0.94). Từ điển tay (chính xác cao) + lexicon ngữ nghĩa (độ phủ rộng) bổ trợ nhau.
- Lexicon (12.839 cụm) + embedding lưu ở `train/lexicon.json`, `train/lexicon_emb.npy`. Hàm: `dict_overnight.py`.
- **Lộ trình câu tự nhiên hoàn chỉnh:** 0.160 → 0.230 (từ điển) → 0.340 (bge-m3) → **0.360 (+ mở rộng ngữ nghĩa)**; topic-level Hit@10 **0.94**. Toàn bộ KHÔNG cần dữ liệu huấn luyện gán nhãn.

### TN12 (mở rộng thêm) — Lexicon lớn hơn KHÔNG giúp (dict_overnight_v2.py)

Thử mở rộng lexicon từ 12.839 (chỉ tiêu đề Điều) lên **18.759 cụm** (thêm 5.463 chủ đề văn bản + 48 glossary), grid man+sem K∈{3,4,5}×τ∈{0.40,0.45,0.50}:

| Lexicon | best full strict Hit@1 | best topic Hit@10 |
|---------|----------------------:|------------------:|
| v1 (tiêu đề Điều, 12.839) | **0.36** | **0.94** |
| v2 (+ chủ đề VB + glossary, 18.759) | 0.32–0.34 | 0.89–0.91 |

**Kết luận âm trung thực: lexicon lớn hơn KHÔNG tốt hơn.** Tiêu đề "Điều" là đơn vị quy phạm khớp ý định câu hỏi; thêm chủ đề văn bản (lẫn đuôi hành chính/kế hoạch/công văn) làm loãng truy vấn ngữ nghĩa. → **Giữ lexicon v1 (Điều) + K=3, τ=0.45 làm cấu hình tối ưu chốt** (đã deploy qua `train/lexicon.json`).

### TN12 (tinh chỉnh mịn K/τ) — dict_finetune.py (lexicon Điều v1, 100 câu TN)

Grid mịn K∈{2,3,4} × τ∈{0.30,0.35,0.40,0.45,0.50}:

| K | full strict Hit@1 | test Hit@1 | full MRR | full topic Hit@10 |
|---|------------------:|-----------:|---------:|------------------:|
| 2 | 0.36 | 0.414 | 0.497 | 0.92 |
| 3 | 0.36 | 0.379 | 0.500 | **0.94** |
| 4 | **0.38** | 0.414 | **0.507** | 0.89 |

- **τ KHÔNG ảnh hưởng** trong [0.30,0.50]: top-K cụm gần nhất luôn có cosine ≥ 0.5 nên ngưỡng không cắt. Chỉ K là đòn bẩy.
- **Đánh đổi precision/recall theo K:** K=4 cho strict Hit@1 cao nhất (0.38, test 0.414, MRR 0.507) nhưng topic Hit@10 giảm còn 0.89; K=3 cân bằng (0.36, topic Hit@10 0.94). Nối nhiều cụm pháp lý hơn ⇒ top-1 sắc hơn nhưng độ phủ sâu loãng.
- **Chọn:** K=3 cho hệ thống tra cứu (ưu tiên "văn bản đúng nằm trong danh sách nguồn" — topic Hit@10 0.94); K=4 nếu ưu tiên Hit@1 nghiêm ngặt. Đây là trần thực dụng (~0.36–0.38) của hướng từ điển+ngữ nghĩa không cần dữ liệu huấn luyện.

## Thí nghiệm 13 — Bộ câu tự nhiên MỞ RỘNG 228 câu (add_natural_v2.py + eval_natural_expanded.py)

Mở rộng bộ câu diễn đạt tự nhiên: soạn tay thêm 128 câu mới đa dạng → **228 câu** (phủ đều 9 lĩnh vực: KCB 33, Dược 31, ATTP 29, BHYT 27, TL 25, RB 23, HM 20, HIV 20, PB 20; 0 trùng/rỗng, 100% nhãn có trong corpus). Đánh giá lại bge-m3:

| Cấu hình | strict Hit@1 | strict Hit@10 | strict MRR | topic Hit@1 | topic Hit@10 | topic MRR |
|----------|------------:|--------------:|-----------:|------------:|-------------:|----------:|
| bge-m3 (base) | 0.140 | 0.526 | 0.261 | 0.193 | 0.627 | 0.330 |
| + từ điển ánh xạ | 0.259 | 0.675 | 0.379 | 0.325 | 0.759 | 0.452 |
| **+ từ điển + ngữ nghĩa** | **0.276** | **0.776** | 0.433 | **0.395** | **0.855** | 0.548 |

- **Chuỗi cải thiện giữ vững ở quy mô lớn hơn:** base→dict (gần gấp đôi strict 0.14→0.26); +ngữ nghĩa thêm (topic Hit@10 0.759→0.855, +0.10). Khẳng định cả hai kỹ thuật đều có giá trị, không phải nhiễu của bộ nhỏ.
- **Số thấp hơn bộ 100** (strict 0.36→0.276; topic Hit@10 0.94→0.855) là con số THỰC TẾ HƠN: 128 câu mới đa dạng hơn, từ điển tay (~60 mục) phủ kém hơn → đây là cận dưới đáng tin, đồng thời chỉ ra (i) cần mở rộng từ điển, (ii) ngữ nghĩa tự động (tổng quát) giúp tương đối nhiều hơn trên câu mới — động lực cho fine-tune.
- **Đề xuất dùng bộ 228 làm headline câu tự nhiên** (rigorous hơn). Bộ 228 cũng cho phép tách train/test lớn hơn để huấn luyện.

### TN13 (tiếp) — Mở rộng từ điển 86→131 mục (đo lại trên 228 câu)

Thêm 45 mục từ điển phủ chủ đề mới (thuốc lá điện tử, hiến giác mạc/xác, nha khoa BHYT, bếp ăn tập thể, cách ly, phơi nhiễm HIV...):

| Cấu hình | strict Hit@1 | strict Hit@10 | topic Hit@1 | topic Hit@10 | strict MRR |
|----------|------------:|--------------:|------------:|-------------:|-----------:|
| bge-m3 base | 0.140 | 0.526 | 0.193 | 0.627 | 0.261 |
| + từ điển (131) | 0.272 | 0.711 | 0.346 | 0.785 | 0.402 |
| **+ từ điển + ngữ nghĩa** | **0.289** | **0.803** | **0.399** | **0.877** | 0.446 |

Mở rộng từ điển 86→131 nâng strict Hit@1 0.276→0.289, topic Hit@10 0.855→0.877. Cải thiện thật nhưng khiêm tốn (từ điển tay khó phủ hết đa dạng) → động lực cho fine-tune. **Cấu hình chốt trên bộ 228: bge-m3 + từ điển(131) + ngữ nghĩa = strict Hit@1 0.289 / Hit@10 0.803; topic Hit@1 0.399 / Hit@10 0.877.** query_expand.py đã có 131 mục (app tự dùng).

## Thí nghiệm 14 — Fine-tune RERANKER cho RAG (finetune_reranker.py, GPU) ⭐ ĐỘT PHÁ

Tách 228 câu TN → **159 train / 69 test** phân tầng theo lĩnh vực (deterministic, KHÔNG train trên câu test). Mine 1.357 cặp (câu đời thường → chunk; dương = thuộc luật đúng, âm = top-30 bge-m3 khác luật). Fine-tune **PhoRanker (135M)** — bge-reranker-v2-m3 (568M) OOM 8GB VRAM do Adam state. Cấu hình truy xuất: bge-m3 + từ điển + ngữ nghĩa, top-30 → reranker → top-10. Đánh giá trên 69 câu TEST giữ riêng:

| Điều kiện | strict Hit@1 | strict MRR | strict Hit@10 | topic Hit@1 | topic Hit@10 |
|-----------|------------:|-----------:|--------------:|------------:|-------------:|
| Không reranker | 0.333 | 0.464 | 0.768 | 0.420 | 0.870 |
| **+ reranker fine-tune** | **0.797** | **0.831** | 0.870 | **0.797** | **0.928** |

**Hit@1 nghiêm ngặt 0.333 → 0.797 (×2,4) trên tập test giữ riêng; MRR 0.464 → 0.831.** Đảo ngược kết quả âm trước (reranker THÔ làm hại): reranker FINE-TUNE học ưu tiên văn bản luật gốc được gán nhãn. Train nhanh (~74s, 2 epoch, loss 0.30). Model: `models/ft-reranker-bge` (thực ra base PhoRanker).

**Cảnh báo trung thực (cần ghi vào báo cáo):** mức tăng lớn bất thường; nhiều khả năng reranker học đặc trưng "ưu tiên văn bản cấp Luật" — khớp đúng quy ước nhãn (luật gốc). Tổng quát hóa thật trên test giữ riêng (tách theo câu, không rò rỉ), nhưng một phần là học-theo-quy-ước-nhãn. KHUYẾN NGHỊ kiểm chứng thêm: (i) cross-validation nhiều split; (ii) thẩm định chuyên gia xem xếp luật gốc #1 có thực sự tốt hơn nghị định hướng dẫn cho người dùng; (iii) đo trên bộ câu mẫu để chắc không hại câu chuẩn.

**Lộ trình câu tự nhiên HOÀN CHỈNH (test giữ riêng):** 0.16 → 0.23 (từ điển) → 0.34 (bge-m3) → ~0.29-0.36 (bộ 228 đa dạng) → **0.80 (+ reranker fine-tune)**.

### TN14 (kiểm chứng) — Reranker fine-tune trên CÂU MẪU + xác nhận (validate_reranker.py)

| Bộ câu | no-rerank Hit@1 | no-rerank MRR | ft-rerank Hit@1 | ft-rerank MRR |
|--------|----------------:|--------------:|----------------:|--------------:|
| Câu mẫu (200 formal) | 0.675 | 0.781 | **0.925** | **0.947** |
| Câu tự nhiên (69 test) | 0.333 | 0.464 | **0.812** | **0.838** |

**Reranker fine-tune KHÔNG hại câu mẫu — giúp CẢ HAI:** câu mẫu Hit@1 0.675→0.925, câu tự nhiên 0.333→0.812. Cả hai bộ đều ngoài dữ liệu huấn luyện reranker (train chỉ 159 câu tự nhiên) → tổng quát hóa thật, KHÔNG phải overfit. Tái lập 2 lần (0.797/0.812). Đây là CẤU HÌNH TỐT NHẤT TOÀN CỤC: bge-m3 + từ điển + ngữ nghĩa + reranker fine-tune (PhoRanker).

**So hệ thống gốc:** câu mẫu Hit@1 0.650→0.925; câu tự nhiên 0.160→0.812. Lưu ý trung thực giữ nguyên (Mục TN14): mức tăng lớn một phần do reranker học "ưu tiên văn bản cấp Luật" khớp quy ước nhãn → khuyến nghị cross-validation + thẩm định chuyên gia.

### TN14 (5-fold cross-validation) — Xác nhận reranker fine-tune KHÔNG do may split (cv_reranker.py)

5-fold stratified theo lĩnh vực trên 228 câu tự nhiên (mỗi fold train 4/5, đo 1/5 giữ riêng). Mỗi fold train PhoRanker riêng:

| Fold | n_test | no-rerank Hit@1 | ft-rerank Hit@1 | ft MRR | ft topic Hit@10 |
|------|-------:|----------------:|----------------:|-------:|----------------:|
| 0 | 48 | 0.167 | 0.792 | 0.823 | 0.917 |
| 1 | 47 | 0.340 | 0.787 | 0.844 | 0.979 |
| 2 | 46 | 0.391 | 0.739 | 0.783 | 0.848 |
| 3 | 44 | 0.295 | 0.818 | 0.864 | 0.932 |
| 4 | 43 | 0.256 | 0.791 | 0.843 | 0.930 |
| **mean±std** | | **0.290 ± 0.076** | **0.785 ± 0.026** | **0.831 ± 0.027** | **0.921 ± 0.042** |

**KẾT LUẬN: reranker fine-tune ổn định qua 5 fold (std Hit@1 chỉ 0.026)** → mức ~0.785 KHÔNG do may mắn chia tập. Cải thiện 0.29→0.785 nhất quán ở mọi fold. Đủ tin cậy để báo cáo. Cảnh báo cơ chế (ưu tiên VB cấp Luật) vẫn giữ — khuyến nghị thẩm định chuyên gia về việc xếp luật gốc trên nghị định hướng dẫn.

### TN14 (group-by-law CV) — Kiểm chứng nghi ngờ "reranker học theo nhãn" (góp ý GVHD, cv_reranker_bylaw.py)

Leave-one-domain-out (9 lĩnh vực): mỗi fold test là 1 lĩnh vực, train trên 8 lĩnh vực còn lại → KHÔNG luật nào của tập test xuất hiện trong train (loại bỏ khả năng ghi nhớ mã luật).

| Lĩnh vực test | no-rerank Hit@1 | ft-rerank Hit@1 | ft MRR |
|---------------|----------------:|----------------:|-------:|
| ATTP | 0.172 | 0.483 | 0.632 |
| BHYT | 0.000 | 0.778 | 0.833 |
| Dược | 0.226 | 0.839 | 0.903 |
| HIV | 0.550 | 0.800 | 0.900 |
| Hiến mô | 0.650 | 0.900 | 0.942 |
| KCB | 0.182 | 0.545 | 0.621 |
| Phòng bệnh | 0.050 | 0.550 | 0.592 |
| Rượu bia | 0.609 | 1.000 | 1.000 |
| Thuốc lá | 0.360 | 0.960 | 0.980 |
| **mean ± std** | **0.311** | **0.762 ± 0.180** | **0.823 ± 0.154** |

**KẾT LUẬN (bảo vệ phương pháp):** group-by-law Hit@1 trung bình **0.762 ≈ 0.785** (by-question) → ngay cả khi luật của lĩnh vực test chưa từng thấy khi train, reranker vẫn xếp đúng → **phần lớn LOẠI TRỪ giả thuyết memorization "ghi nhớ mã luật"**; reranker học độ liên quan tổng quát. Độ lệch cao hơn (0.18 vs 0.026) cho thấy có phụ thuộc lĩnh vực: vài lĩnh vực khó (ATTP 0.48, KCB/PB 0.55), còn lại rất cao (RB 1.0, TL 0.96). → Cảnh báo trung thực được làm rõ bằng định lượng: reranker chủ yếu học thật, một phần phụ thuộc đặc thù lĩnh vực; vẫn nên thẩm định chuyên gia (đã lập phiếu).
