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
