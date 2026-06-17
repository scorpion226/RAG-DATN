# Kịch bản video demo — Hệ thống RAG tra cứu văn bản Pháp luật/Y tế

**Thời lượng mục tiêu:** 4–6 phút · **Định dạng:** quay màn hình (web demo) + lồng tiếng.
**Chuẩn bị trước khi quay:**
```powershell
# Bật cấu hình tốt nhất (bge-m3 + từ điển + ngữ nghĩa + reranker fine-tune) + LLM thật
$env:USE_BGE=1; $env:LLM_MODE="gguf"
uvicorn app:app --port 8000
# Mở http://localhost:8000, đợi /health trả "ok" (model nạp ~90s) rồi mới quay.
```

---

## Cảnh 1 — Mở đầu (0:00–0:30)
**Hình:** slide tiêu đề / trang chủ web.
**Lời thoại:**
> "Xin chào quý thầy cô. Em xin trình bày demo Hệ thống RAG hỗ trợ tra cứu văn bản pháp luật ngành y tế Việt Nam. Hệ thống nhận câu hỏi tiếng Việt, truy xuất các văn bản liên quan và sinh câu trả lời kèm trích dẫn — toàn bộ chạy cục bộ trên máy CPU, không cần Internet."

## Cảnh 2 — Câu hỏi pháp lý chuẩn (0:30–1:30)
**Thao tác:** gõ câu hỏi mang thuật ngữ pháp lý.
**Câu mẫu:**
> "Điều kiện cấp giấy phép hành nghề khám bệnh, chữa bệnh là gì?"

**Lời thoại (khi kết quả hiện):**
> "Hệ thống trả về câu trả lời bám điều luật, kèm danh sách nguồn: số hiệu văn bản, tình trạng hiệu lực và trích đoạn. Mọi khẳng định đều dẫn về văn bản gốc — điều bắt buộc trong lĩnh vực pháp lý."
**Nhấn mạnh:** chỉ vào thẻ nguồn (vd Luật 15/2023/QH15) và nhãn "Còn hiệu lực".

## Cảnh 3 — Truy vấn theo số hiệu (1:30–2:15)
**Câu mẫu:**
> "Nghị định 96/2023/NĐ-CP quy định gì?"

**Lời thoại:**
> "Với truy vấn chứa số hiệu, hệ thống nhận diện và trả về đúng văn bản đó — điểm yếu cố hữu của tìm kiếm ngữ nghĩa thuần, được khắc phục bằng cơ chế hybrid kết hợp BM25 và nhận diện số hiệu."

## Cảnh 4 — Câu hỏi ĐỜI THƯỜNG (điểm nhấn) (2:15–3:45)
**Thao tác:** gõ các câu hỏi kiểu người dân, KHÔNG dùng thuật ngữ pháp lý.
**Câu mẫu (chạy 2–3 câu):**
> "Mở quán ăn nhỏ có cần xin giấy vệ sinh an toàn thực phẩm không?"
> "Tôi muốn mở quầy thuốc ở quê thì cần bằng cấp gì?"
> "Hút thuốc lá điện tử nơi công cộng có bị cấm không?"

**Lời thoại:**
> "Đây là thách thức lớn nhất: người dân hỏi bằng ngôn ngữ đời thường, khác hẳn thuật ngữ trong văn bản. Hệ thống dùng ba kỹ thuật — mô hình embedding đa ngữ bge-m3, từ điển ánh xạ đời thường sang pháp lý, và mở rộng ngữ nghĩa — rồi xếp hạng lại bằng reranker đã tinh chỉnh. Nhờ đó, câu hỏi 'mở quán ăn nhỏ' vẫn trả về đúng Luật An toàn thực phẩm."
**Nhấn mạnh:** chỉ vào top-1 là đúng Luật gốc cho từng câu.

## Cảnh 5 — Con số kết quả (3:45–4:45)
**Hình:** slide hành trình cải thiện (natural_journey) + bảng kết quả.
**Lời thoại:**
> "Trên bộ đánh giá, độ chính xác top-1 cho câu hỏi đời thường tăng từ 0,16 lên 0,785 qua kiểm chứng chéo 5-fold; câu hỏi chuẩn đạt 0,925. Quan trọng, đề tài báo cáo trung thực cả những hướng chưa thành công và nêu rõ cần thẩm định chuyên gia cho bước reranker."

## Cảnh 6 — Kết (4:45–5:15)
**Hình:** trang chủ / slide cảm ơn.
**Lời thoại:**
> "Hệ thống minh họa một pipeline RAG tiếng Việt hoàn chỉnh, vận hành trên máy phổ thông, có thể mở rộng sang các lĩnh vực pháp luật khác. Em xin cảm ơn và mong nhận góp ý của Hội đồng."

---

## Mẹo quay
- Quay 1080p, phóng to khung chat cho dễ đọc; ẩn thanh bookmark trình duyệt.
- Mỗi câu hỏi: chờ trả lời xong rồi hãy cuộn xem nguồn (đừng cắt giữa lúc đang sinh).
- Nếu sinh trên CPU chậm (~30–45s/câu), có thể cắt dựng (tua nhanh) đoạn chờ.
- Câu hỏi dự phòng (nếu một câu cho kết quả chưa đẹp): "Bác sĩ có được từ chối chữa cho bệnh nhân không?", "Sinh viên có bắt buộc mua bảo hiểm y tế không?", "Bán thuốc giả bị xử lý thế nào?".
- Tổng thời lượng nên ≤ 6 phút; nếu cần ngắn, bỏ Cảnh 3.
