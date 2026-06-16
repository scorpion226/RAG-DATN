# -*- coding: utf-8 -*-
"""Mở rộng bộ câu hỏi DIỄN ĐẠT TỰ NHIÊN (soạn tay): thêm ~140 câu đời thường mới, đa dạng,
phủ 9 lĩnh vực luật y tế. Gán nhãn = luật điều chỉnh. Khử trùng theo nội dung.
Chạy: python eval/add_natural_v2.py  -> ghi đè golden_questions.json"""
import os, json, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "golden_questions.json")

KCB = ["15/2023/QH15"]
DUOC = ["105/2016/QH13", "44/2024/QH15", "39/VBHN-VPQH"]
ATTP = ["55/2010/QH12", "61/VBHN-VPQH", "02/VBHN-VPQH"]
BHYT = ["46/2014/QH13", "51/2024/QH15"]
TL = ["09/2012/QH13", "08/VBHN-VPQH", "11/VBHN-VPQH", "15/VBHN-VPQH"]
RB = ["44/2019/QH14"]
HM = ["75/2006/QH11"]
HIV = ["64/2006/QH11", "33/VBHN-VPQH"]
PB = ["114/2025/QH15"]

NEW = [
    # ---- Khám bệnh, chữa bệnh (16) ----
    ("Đi khám mà muốn đổi sang bác sĩ khác có được không?", KCB),
    ("Bệnh viện có được giữ người lại khi chưa đóng đủ viện phí không?", KCB),
    ("Bác sĩ đã nghỉ hưu có được mở phòng khám riêng không?", KCB),
    ("Người bệnh có quyền đọc bệnh án của mình ngay tại viện không?", KCB),
    ("Bác sĩ có được nhận phong bì, quà của bệnh nhân không?", KCB),
    ("Y sĩ có được khám và kê đơn như bác sĩ không?", KCB),
    ("Bệnh viện tư có được từ chối cấp cứu người không mang tiền không?", KCB),
    ("Người chưa có chứng chỉ hành nghề có được trực tiếp mổ cho bệnh nhân không?", KCB),
    ("Bác sĩ làm sai khiến bệnh nhân nặng thêm thì chịu trách nhiệm gì?", KCB),
    ("Muốn mở một bệnh viện tư nhân cần xin phép những gì?", KCB),
    ("Bệnh nhân hấp hối có quyền từ chối tiếp tục điều trị không?", KCB),
    ("Người nước ngoài qua Việt Nam chữa bệnh có được không?", KCB),
    ("Bác sĩ có được quảng cáo dịch vụ khám chữa bệnh trên mạng không?", KCB),
    ("Phòng khám phải công khai bảng giá ở đâu cho bệnh nhân biết?", KCB),
    ("Người hành nghề bị bệnh truyền nhiễm có được tiếp tục khám không?", KCB),
    ("Bệnh viện có phải xin phép người bệnh trước khi phẫu thuật không?", KCB),
    # ---- Dược (16) ----
    ("Mua thuốc kháng sinh ở nhà thuốc có cần đơn bác sĩ không?", DUOC),
    ("Nhà thuốc có được bán thuốc đã quá hạn sử dụng không?", DUOC),
    ("Người không học dược có được mở nhà thuốc rồi thuê dược sĩ không?", DUOC),
    ("Bán thuốc trên Facebook, Shopee có vi phạm gì không?", DUOC),
    ("Thuốc nhập lậu, không rõ nguồn gốc bị xử lý ra sao?", DUOC),
    ("Nhà thuốc có được tự pha chế thuốc bán cho khách không?", DUOC),
    ("Thuốc gây nghiện được kê và bán như thế nào?", DUOC),
    ("Một người có được mở nhiều nhà thuốc ở nhiều nơi không?", DUOC),
    ("Dược sĩ thực tập có được tự bán thuốc khi chủ vắng không?", DUOC),
    ("Thực phẩm chức năng bán ở nhà thuốc có cần đăng ký gì không?", DUOC),
    ("Thuốc hiếm không có ở Việt Nam thì xin nhập về cho bệnh nhân thế nào?", DUOC),
    ("Quảng cáo thuốc phải xin phép cơ quan nào?", DUOC),
    ("Bán thuốc tránh thai, thuốc cảm có cần đơn không?", DUOC),
    ("Nhà thuốc bị phát hiện bán thuốc giả thì bị xử lý gì?", DUOC),
    ("Giá thuốc trong bệnh viện do ai quyết định?", DUOC),
    ("Người dân mua thuốc xách tay từ nước ngoài về dùng có sao không?", DUOC),
    # ---- An toàn thực phẩm (16) ----
    ("Bán bánh mì, xôi vỉa hè có phải xin giấy phép gì không?", ATTP),
    ("Quán trà sữa cần điều kiện gì về vệ sinh an toàn thực phẩm?", ATTP),
    ("Làm đồ ăn bán online tại nhà có cần giấy chứng nhận không?", ATTP),
    ("Thực phẩm hết hạn bày bán trong siêu thị bị xử lý sao?", ATTP),
    ("Nhà hàng để khách bị ngộ độc thì phải bồi thường thế nào?", ATTP),
    ("Dùng hàn the, phẩm màu công nghiệp trong thực phẩm bị phạt gì?", ATTP),
    ("Rau bán ngoài chợ có bắt buộc kiểm tra thuốc trừ sâu không?", ATTP),
    ("Nước đá dùng cho quán ăn phải đảm bảo gì?", ATTP),
    ("Người bán hàng ăn có bắt buộc khám sức khỏe không?", ATTP),
    ("Thịt heo bán ngoài chợ có cần dấu kiểm dịch không?", ATTP),
    ("Cơ sở làm giò chả cần đáp ứng điều kiện gì?", ATTP),
    ("Quảng cáo thực phẩm chức năng nói chữa được bệnh có bị cấm không?", ATTP),
    ("Bếp ăn tập thể của trường học, công ty phải đảm bảo gì?", ATTP),
    ("Đồ ăn nhập khẩu phải ghi nhãn tiếng Việt thế nào?", ATTP),
    ("Ai chịu trách nhiệm kiểm tra an toàn thực phẩm ở chợ?", ATTP),
    ("Bán hải sản tươi sống cần bảo quản theo quy định nào?", ATTP),
    # ---- Bảo hiểm y tế (15) ----
    ("Đi cấp cứu ở bệnh viện khác tỉnh có được bảo hiểm trả không?", BHYT),
    ("Sinh con thì bảo hiểm y tế chi trả những khoản gì?", BHYT),
    ("Thẻ bảo hiểm y tế bị sai tên thì sửa ở đâu?", BHYT),
    ("Người thất nghiệp có được tiếp tục dùng bảo hiểm y tế không?", BHYT),
    ("Khám răng, làm răng có được bảo hiểm y tế chi trả không?", BHYT),
    ("Bao lâu sau khi mua thẻ bảo hiểm y tế mới được dùng?", BHYT),
    ("Người nước ngoài làm việc ở Việt Nam có phải đóng bảo hiểm y tế không?", BHYT),
    ("Tự đi khám không qua tuyến dưới thì bảo hiểm trả bao nhiêu?", BHYT),
    ("Mua thuốc theo đơn ngoài bệnh viện có được bảo hiểm trả không?", BHYT),
    ("Người trên 80 tuổi có được nhà nước mua bảo hiểm y tế không?", BHYT),
    ("Đóng bảo hiểm y tế bị gián đoạn vài tháng thì có sao không?", BHYT),
    ("Học sinh đóng bảo hiểm y tế ở trường hay tự đi mua?", BHYT),
    ("Bị tai nạn giao thông có được bảo hiểm y tế chi trả không?", BHYT),
    ("Cả gia đình cùng mua bảo hiểm y tế thì có được giảm tiền không?", BHYT),
    ("Bảo hiểm y tế chi trả tối đa bao nhiêu cho một đợt điều trị?", BHYT),
    # ---- Thuốc lá (14) ----
    ("Hút thuốc lá điện tử nơi công cộng có bị cấm không?", TL),
    ("Quán karaoke, quán bar có được cho khách hút thuốc không?", TL),
    ("Bán thuốc lá lẻ từng điếu có vi phạm không?", TL),
    ("Cửa hàng tạp hóa bán thuốc lá có cần giấy phép không?", TL),
    ("Hút thuốc ở bến xe, sân bay có bị phạt không?", TL),
    ("Trên bao thuốc lá bắt buộc in những cảnh báo gì?", TL),
    ("Quảng cáo thuốc lá trên mạng có bị cấm không?", TL),
    ("Người dưới 18 tuổi hút thuốc có bị xử lý không?", TL),
    ("Khuyến mãi, tặng kèm thuốc lá có được phép không?", TL),
    ("Trong nhà có trẻ nhỏ, hút thuốc có vi phạm pháp luật không?", TL),
    ("Công ty thuốc lá có được tài trợ chương trình truyền hình không?", TL),
    ("Nhập khẩu thuốc lá điện tử về bán có hợp pháp không?", TL),
    ("Cơ quan, công sở có bắt buộc cấm hút thuốc không?", TL),
    ("Tiền thu được từ thuế thuốc lá dùng vào việc gì?", TL),
    # ---- Rượu bia (13) ----
    ("Bán rượu cho người đã say xỉn có vi phạm không?", RB),
    ("Cửa hàng tạp hóa bán rượu cần giấy phép gì?", RB),
    ("Quảng cáo bia trên mạng xã hội có bị hạn chế không?", RB),
    ("Cho con nít uống rượu trong đám tiệc có vi phạm không?", RB),
    ("Bán rượu gần trường học có bị cấm không?", RB),
    ("Uống rượu trong giờ làm việc ở cơ quan có vi phạm không?", RB),
    ("Tổ chức tiệc có ép nhau uống rượu thì sao?", RB),
    ("Bán rượu tự nấu ở quê có cần đăng ký không?", RB),
    ("Có được bán rượu bia trong bệnh viện, trường học không?", RB),
    ("Người chưa đủ tuổi mua rượu hộ người lớn có bị phạt không?", RB),
    ("Quán nhậu mở quá khuya bán rượu có bị cấm giờ không?", RB),
    ("Tài trợ giải bóng đá bằng thương hiệu bia có được không?", RB),
    ("Phụ nữ mang thai uống rượu pháp luật khuyến cáo thế nào?", RB),
    # ---- Hiến mô tạng (12) ----
    ("Muốn hiến giác mạc sau khi qua đời thì đăng ký ở đâu?", HM),
    ("Người dưới 18 tuổi có được hiến tạng không?", HM),
    ("Hiến xác cho trường y để nghiên cứu thì làm thủ tục thế nào?", HM),
    ("Gia đình có được bán tạng của người thân đã mất không?", HM),
    ("Người hiến thận khi còn sống được khám sức khỏe miễn phí không?", HM),
    ("Ai là người quyết định lấy tạng khi người hiến đã chết não?", HM),
    ("Có được chọn người nhận tạng mình hiến không?", HM),
    ("Hiến tủy xương cho người lạ có được không?", HM),
    ("Người hiến tạng đã mất có được tổ chức tang lễ chu đáo không?", HM),
    ("Đăng ký hiến tạng rồi có được đổi ý rút lại không?", HM),
    ("Bệnh viện nào được phép lấy và ghép tạng?", HM),
    ("Mua bán nội tạng qua môi giới bị xử lý thế nào?", HM),
    # ---- HIV/AIDS (12) ----
    ("Xét nghiệm HIV ở đâu được giữ bí mật?", HIV),
    ("Công ty có được sa thải nhân viên vì nhiễm HIV không?", HIV),
    ("Trẻ nhiễm HIV có được nhận vào trường mầm non không?", HIV),
    ("Bác sĩ có được tiết lộ tình trạng HIV của bệnh nhân cho người khác không?", HIV),
    ("Người nhiễm HIV có được kết hôn, sinh con không?", HIV),
    ("Bị kim tiêm đâm phải, sợ lây HIV thì làm gì?", HIV),
    ("Người nhiễm HIV cố tình lây cho người khác bị xử lý sao?", HIV),
    ("Phụ nữ mang thai nhiễm HIV được hỗ trợ gì để con không bị lây?", HIV),
    ("Thuốc điều trị HIV có được cấp miễn phí không?", HIV),
    ("Cơ sở cai nghiện có được xét nghiệm HIV bắt buộc không?", HIV),
    ("Người nhiễm HIV có được đi nghĩa vụ quân sự không?", HIV),
    ("Quảng cáo kỳ thị người nhiễm HIV có bị xử lý không?", HIV),
    # ---- Phòng bệnh, tiêm chủng, dịch (14) ----
    ("Trẻ sơ sinh bắt buộc tiêm những mũi vắc xin nào?", PB),
    ("Không cho con tiêm vắc xin bắt buộc thì cha mẹ có bị phạt không?", PB),
    ("Tiêm vắc xin xong bị sốc phản vệ thì ai chịu trách nhiệm?", PB),
    ("Khi có dịch bệnh, nhà nước được phong tỏa khu dân cư không?", PB),
    ("Người từ vùng dịch về có bắt buộc cách ly không?", PB),
    ("Trốn khai báo y tế khi đang có dịch bị xử lý thế nào?", PB),
    ("Bệnh truyền nhiễm nhóm A gồm những bệnh gì?", PB),
    ("Người mắc bệnh truyền nhiễm có bị bắt buộc chữa trị không?", PB),
    ("Cơ sở y tế phải báo cáo dịch bệnh cho ai?", PB),
    ("Phun thuốc diệt muỗi phòng sốt xuất huyết do ai tổ chức?", PB),
    ("Vắc xin tiêm chủng mở rộng có phải trả tiền không?", PB),
    ("Cách ly y tế bắt buộc tối đa bao nhiêu ngày?", PB),
    ("Người chống đối lệnh cách ly bị xử lý ra sao?", PB),
    ("Nhập cảnh Việt Nam có phải kiểm dịch y tế không?", PB),
]


def main():
    cur = json.load(open(PATH, encoding="utf-8"))
    seen = {q["q"].strip().lower() for q in cur}
    added = 0
    for q, rel in NEW:
        key = q.strip().lower()
        if key in seen:
            continue
        cur.append({"q": q, "relevant": rel, "type": "natural"})
        seen.add(key); added += 1
    json.dump(cur, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_nat = sum(1 for q in cur if q.get("type") == "natural")
    print(f"Thêm {added} câu tự nhiên mới. Tổng câu tự nhiên: {n_nat}. Tổng bộ: {len(cur)}")


if __name__ == "__main__":
    main()
