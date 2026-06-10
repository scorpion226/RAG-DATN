# Kết quả đánh giá Retrieval (cho báo cáo)

**Bộ test:** 18 câu hỏi vàng (`golden_questions.json`) neo vào các luật y tế.
**Ground-truth:** văn bản luật điều chỉnh câu hỏi + **bản hợp nhất (VBHN) tương đương** của luật đó
(vd `39/VBHN-VPQH` = hợp nhất Luật Dược) — vì VBHN có cùng nội dung luật nhưng khác số hiệu.
**Index:** 367,462 chunk (toàn corpus). **Chỉ số:** Hit@k, MRR.

## Bảng tổng hợp (cùng ground-truth, 18 câu)

| Cấu hình | Hit@1 | Hit@3 | Hit@5 | Hit@10 | MRR |
|----------|------:|------:|------:|-------:|----:|
| (1) Không tách từ              | 0.333 | 0.556 | 0.667 | 0.833 | 0.481 |
| (2) Vector + tách từ pyvi      | 0.389 | 0.778 | 0.833 | 0.944 | 0.586 |
| (3) Vector + Reranker          | 0.500 | 0.833 | 0.889 | 0.889 | 0.644 |
| (4) Hybrid (BM25+vector, RRF)  | 0.556 | 0.778 | 0.889 | **1.000** | 0.687 |
| (5) Hybrid + Reranker          | **0.556** | **0.833** | **0.944** | 0.944 | **0.722** |

Lệnh: `evaluate.py` (2), `--no-segment` (1), `--rerank` (3), `--hybrid` (4), `--hybrid --rerank` (5).

## Diễn giải (từng bước được chứng minh)

**Bước A — Tách từ pyvi** [(1)→(2)]: Hit@3 **0.556 → 0.778 (+0.222)**, MRR +0.105.
Lý do: PhoBERT huấn luyện trên text đã tách từ; tách từ nhất quán index↔truy vấn giúp khớp embedding.

**Bước B — Reranker cross-encoder (PhoRanker)** [(2)→(3)]: Hit@1 **0.389 → 0.500 (+0.111)**, MRR +0.058.
Lý do: cross-encoder đọc đồng thời (câu hỏi+đoạn) nên xếp hạng tinh hơn cosine của bi-encoder.
Đánh đổi: Hit@10 giảm nhẹ (chỉ xếp lại top-30) — có thể tăng số ứng viên để giảm.

**Bước C — Hybrid BM25+vector (RRF)** [(2)→(4)]: Hit@1 **0.389 → 0.556 (+0.167)**, **Hit@10 = 1.000**, MRR +0.101.
Lý do: BM25 bù điểm yếu từ vựng/số hiệu của vector; RRF hợp nhất theo thứ hạng. Thêm nhận diện
số hiệu văn bản (regex) → tiêm thẳng chunk đúng số hiệu (vector thuần thường trượt — vd "96/2023/NĐ-CP").

**Tốt nhất — Hybrid + Reranker** (5): MRR **0.722**, Hit@5 **0.944**. Đây là cấu hình đề xuất cho hệ thống.

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
