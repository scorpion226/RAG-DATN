# Kịch bản Video Demo — Hệ thống RAG tra cứu pháp luật/y tế

Mục tiêu video: ~5–7 phút, cho thấy (1) cách chạy hệ thống, (2) các kịch bản thử nghiệm, (3) chất lượng câu trả lời và trích dẫn.

## A. Chuẩn bị trước khi quay
- [ ] Đã có chỉ mục: `chroma_db/` (367.462 vector) và `bm25_index/`.
- [ ] Đã tải mô hình: `models/PhoGPT-4B-Chat-Q4_K_M.gguf`.
- [ ] Mở sẵn 2 cửa sổ: Terminal (PowerShell) và trình duyệt.

## B. Phần 1 — Giới thiệu (≈ 45 giây)
Lời thuyết minh gợi ý:
> “Đây là hệ thống RAG hỗ trợ tra cứu văn bản pháp luật ngành y tế Việt Nam. Hệ thống truy xuất các đoạn văn bản liên quan từ kho 367.462 đoạn (21.490 văn bản còn hiệu lực), rồi dùng mô hình PhoGPT sinh câu trả lời kèm trích dẫn số hiệu văn bản. Toàn bộ chạy trên CPU.”

## C. Phần 2 — Cách chạy chương trình (≈ 1,5 phút)
Quay màn hình Terminal, gõ lần lượt (giải thích từng bước):
```powershell
# 1) (nếu chưa có) tạo chỉ mục
python build_chunks.py            # tạo dữ liệu đoạn
python index_chroma.py            # embedding + ChromaDB
python build_bm25.py              # chỉ mục BM25

# 2) chạy web (PhoGPT + hybrid + reranker)
$env:LLM_MODE="gguf"; $env:USE_HYBRID="1"; $env:USE_RERANK="1"
uvicorn app:app --port 8000
```
> Mở trình duyệt `http://localhost:8000`. Lưu ý: câu hỏi đầu tiên mất ~90s nạp mô hình, các câu sau ~20–40s.

## D. Phần 3 — Các kịch bản thử nghiệm (≈ 3 phút)
Quay trình duyệt, lần lượt hỏi các câu sau (đa lĩnh vực) và chỉ ra **câu trả lời + nguồn trích dẫn**:

| # | Lĩnh vực | Câu hỏi demo | Kỳ vọng (nguồn) |
|---|----------|--------------|------------------|
| 1 | Khám chữa bệnh | Điều kiện để cá nhân được cấp giấy phép hành nghề khám bệnh, chữa bệnh? | Luật 15/2023/QH15 |
| 2 | Dược | Những hành vi bị nghiêm cấm trong hoạt động dược? | Luật Dược 105/2016/QH13 |
| 3 | An toàn thực phẩm | Cơ sở kinh doanh thực phẩm phải bảo đảm điều kiện gì? | Luật ATTP 55/2010/QH12 |
| 4 | Bảo hiểm y tế | Đối tượng nào tham gia bảo hiểm y tế bắt buộc? | Luật BHYT 46/2014, 51/2024 |
| 5 | Thuốc lá | Những địa điểm nào cấm hút thuốc lá hoàn toàn? | Luật 09/2012/QH13 |
| 6 | Tra cứu theo số hiệu | Nội dung Nghị định 96/2023/NĐ-CP quy định gì? | đúng VB 96/2023/NĐ-CP |
| 7 | Ngoài phạm vi (kiểm tra chống bịa) | Thủ tục đăng ký kết hôn? | hệ thống nói “không tìm thấy trong VB y tế” |

Điểm cần nhấn mạnh khi quay:
- Câu trả lời **bám văn bản**, có **trích dẫn số hiệu**.
- Mở thẻ **“nguồn tham khảo”** để thấy số hiệu / loại VB / tình trạng hiệu lực / điểm liên quan.
- Câu #6 minh họa **hybrid bắt đúng số hiệu** (vector thuần hay trượt).
- Câu #7 minh họa hệ thống **không bịa** khi ngoài phạm vi.

## E. Phần 4 — Kết quả đánh giá (≈ 45 giây)
- Mở `eval/results.md` hoặc `report/figs/retrieval_comparison.png`.
> “Trên bộ 18 câu hỏi vàng, cấu hình Hybrid + Reranker đạt MRR 0,722 và Hit@10 tới 1,000. Mỗi kỹ thuật (tách từ, reranker, hybrid) đều được kiểm chứng bằng thí nghiệm A/B.”

## F. Kết (≈ 15 giây)
> “Hệ thống đã chạy hoàn chỉnh đầu–cuối trên CPU, mã nguồn và hướng dẫn có tại GitHub. Cảm ơn thầy/cô đã theo dõi.”

---
*Mẹo quay:* dùng OBS Studio (miễn phí) để quay màn hình; thu nhỏ cửa sổ còn ~1280×800 cho rõ; nói chậm, dừng vài giây ở mỗi câu trả lời để người xem đọc kịp.
