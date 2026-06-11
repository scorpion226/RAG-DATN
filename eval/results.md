# Kết quả đánh giá Retrieval (cho báo cáo)

**Bộ test:** 50 câu hỏi vàng (`golden_questions.json`) neo vào các luật y tế (|relevant| TB 1,96).
**Ground-truth:** văn bản luật điều chỉnh câu hỏi + **bản hợp nhất (VBHN) tương đương** của luật đó
(vd `39/VBHN-VPQH` = hợp nhất Luật Dược) — vì VBHN có cùng nội dung luật nhưng khác số hiệu.
**Index:** 367,462 chunk (toàn corpus). **Chỉ số:** Hit@k, MRR, Precision/Recall/F1@k.

## Bảng tổng hợp (cùng ground-truth, 50 câu)

| Cấu hình | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|----------|------:|------:|------:|-------:|----:|
| (1) Không tách từ              | 0.380 | 0.640 | 0.720 | 0.840 | 0.534 |
| (2) Vector + tách từ pyvi      | 0.520 | 0.820 | 0.860 | 0.920 | 0.668 |
| (3) Vector + Reranker          | 0.540 | 0.780 | 0.840 | 0.880 | 0.667 |
| (4) Hybrid (BM25+vector, RRF)  | 0.500 | 0.800 | 0.860 | **0.980** | 0.669 |
| (5) Hybrid + Reranker          | **0.560** | 0.780 | 0.860 | 0.920 | **0.694** |

*(Bộ 18 câu trước đó cho kết quả gần như tương đương: Hit@1 0.556, MRR 0.722 → khẳng định tính ổn định.)*

Lệnh: `evaluate.py` (2), `--no-segment` (1), `--rerank` (3), `--hybrid` (4), `--hybrid --rerank` (5).

## Diễn giải (từng bước được chứng minh)

**Bước A — Tách từ pyvi** [(1)→(2)]: Hit@1 **0.380 → 0.520 (+0.140)**, Hit@3 **0.640 → 0.820 (+0.180)**, MRR +0.134.
Lý do: PhoBERT huấn luyện trên text đã tách từ; tách từ nhất quán index↔truy vấn giúp khớp embedding. (Đòn bẩy mạnh nhất.)

**Bước B — Reranker cross-encoder (PhoRanker)** [(2)→(3)]: Hit@1 **0.520 → 0.540 (+0.020)**, MRR ~đi ngang.
Trên bộ 50 câu reranker đơn lẻ lợi ích nhỏ; nhưng kết hợp với hybrid (5) cho Hit@1 và MRR cao nhất → reranker hiệu quả hơn khi đứng sau tập ứng viên đa dạng.

**Bước C — Hybrid BM25+vector (RRF)** [(2)→(4)]: **Hit@10 = 0.980** (cao nhất, gần như không bỏ sót).
Lý do: BM25 bù điểm yếu từ vựng/số hiệu của vector; RRF hợp nhất theo thứ hạng. Thêm nhận diện
số hiệu văn bản (regex) → tiêm thẳng chunk đúng số hiệu (vector thuần thường trượt — vd "96/2023/NĐ-CP").

**Tốt nhất — Hybrid + Reranker** (5): Hit@1 **0.560**, MRR **0.694**. Đây là cấu hình đề xuất cho hệ thống.

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
| 1 | 0.560 | 0.363 | 0.440 | 1.000 |
| 3 | 0.360 | 0.632 | **0.459** | 0.653 |
| 5 | 0.244 | 0.688 | 0.360 | 0.392 |
| 10 | 0.140 | 0.778 | 0.237 | 0.196 |

- F1 cực đại tại **k=3** → lấy 3–5 nguồn là cân bằng tốt (đánh đổi Precision↓/Recall↑).
- **Trần Precision:** do |relevant| TB 1,96, P bị chặn trần min(|rel|,k)/k. Precision giảm theo k chủ yếu do trần giảm — tỷ lệ đạt-trần TĂNG 56%→71% → truy xuất không kém đi.
- **Thời gian (CPU, 50 câu):** truy xuất TB ~7,4s; sinh TB ~45s.
- **Mức độ trích dẫn:** 6/6 câu sinh (100%) trích dẫn đúng văn bản liên quan; bám điều luật (Điều 19/33/79).
- Quan sát: mô hình đôi khi nêu chi tiết phụ chưa chính xác (vd nhắc "Luật 2009" dù nguồn là 15/2023/QH15) → RAG giảm nhưng chưa loại bỏ hết sai sót phần sinh.
