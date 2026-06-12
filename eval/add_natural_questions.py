# -*- coding: utf-8 -*-
"""Bổ sung 30 câu hỏi DIỄN ĐẠT TỰ NHIÊN (kiểu người dân hỏi, không trùng từ vựng luật)
vào golden_questions.json, gắn nhãn type='natural' để đo riêng.
Chạy: python eval/add_natural_questions.py"""
import sys, os, json
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))

KCB = ["15/2023/QH15"]
DUOC = ["105/2016/QH13", "44/2024/QH15", "39/VBHN-VPQH"]
ATTP = ["55/2010/QH12", "61/VBHN-VPQH", "02/VBHN-VPQH"]
BHYT = ["46/2014/QH13", "51/2024/QH15"]
TL = ["09/2012/QH13", "08/VBHN-VPQH", "11/VBHN-VPQH", "15/VBHN-VPQH"]
RB = ["44/2019/QH14"]
HM = ["75/2006/QH11"]
HIV = ["64/2006/QH11", "33/VBHN-VPQH"]
PB = ["114/2025/QH15"]

NATURAL = [
    # Khám chữa bệnh (5)
    ("Tôi vừa tốt nghiệp bác sĩ đa khoa, muốn được đi làm khám chữa bệnh thì phải làm những gì?", KCB),
    ("Bác sĩ có được từ chối chữa cho bệnh nhân không?", KCB),
    ("Đi khám bệnh mà không hài lòng, người bệnh có quyền khiếu nại hay yêu cầu gì không?", KCB),
    ("Phòng khám tư nhân muốn mở cửa hoạt động thì cần giấy tờ gì?", KCB),
    ("Bác sĩ nước ngoài sang Việt Nam làm việc có cần biết tiếng Việt không?", KCB),
    # Dược (5)
    ("Tôi muốn mở quầy thuốc ở quê thì cần bằng cấp và điều kiện gì?", DUOC),
    ("Bán thuốc giả, thuốc kém chất lượng thì bị xử lý thế nào?", DUOC),
    ("Quảng cáo thuốc trên mạng xã hội có được phép không?", DUOC),
    ("Nhà thuốc có được tự ý tăng giá thuốc không?", DUOC),
    ("Ai được đứng tên chịu trách nhiệm chuyên môn cho một nhà thuốc?", DUOC),
    # ATTP (4)
    ("Mở quán ăn nhỏ có cần xin giấy chứng nhận vệ sinh an toàn thực phẩm không?", ATTP),
    ("Bán rau quả tươi ngoài chợ phải đảm bảo những gì để an toàn?", ATTP),
    ("Hàng xách tay là đồ ăn nhập từ nước ngoài về bán có phải kiểm tra gì không?", ATTP),
    ("Trên bao bì đồ ăn phải ghi những thông tin gì?", ATTP),
    # BHYT (4)
    ("Sinh viên có bắt buộc phải mua bảo hiểm y tế không?", BHYT),
    ("Mỗi tháng phải đóng bao nhiêu tiền bảo hiểm y tế, ai trả?", BHYT),
    ("Có thẻ BHYT thì đi viện được giảm những khoản nào?", BHYT),
    ("Trường hợp nào đi viện mà bảo hiểm y tế không chi trả?", BHYT),
    # Thuốc lá (4)
    ("Hút thuốc trong bệnh viện có bị phạt không?", TL),
    ("Vì sao trên vỏ bao thuốc lá phải in hình cảnh báo ghê rợn?", TL),
    ("Bán thuốc lá cho trẻ em dưới 18 tuổi có bị cấm không?", TL),
    ("Người không hút thuốc có quyền yêu cầu người khác không hút gần mình không?", TL),
    # Rượu bia (3)
    ("Uống bia rồi lái xe máy về nhà có vi phạm pháp luật không?", RB),
    ("Quán nhậu có được bán rượu cho học sinh không?", RB),
    ("Quảng cáo bia trên tivi giờ vàng có bị hạn chế gì không?", RB),
    # Hiến mô tạng (2)
    ("Tôi muốn đăng ký hiến tạng sau khi qua đời thì làm thủ tục ở đâu, thế nào?", HM),
    ("Mua bán thận có bị pháp luật cấm không?", HM),
    # HIV (2)
    ("Người nhiễm HIV có bị đuổi việc hay đuổi học không?", HIV),
    ("Công ty có được yêu cầu xét nghiệm HIV khi tuyển dụng không?", HIV),
    # Phòng bệnh (1)
    ("Trẻ em có được tiêm vắc xin miễn phí không, chương trình nào?", PB),
]


def main():
    path = os.path.join(HERE, "golden_questions.json")
    data = json.load(open(path, encoding="utf-8"))
    seen = {q["q"].strip().lower() for q in data}
    added = 0
    for q, rel in NATURAL:
        if q.strip().lower() in seen:
            continue
        data.append({"q": q, "relevant": rel, "type": "natural"})
        added += 1
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    nat = sum(1 for x in data if x.get("type") == "natural")
    print(f"Đã thêm {added} câu tự nhiên. Tổng: {len(data)} câu (natural: {nat}).")


if __name__ == "__main__":
    main()
