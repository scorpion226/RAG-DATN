# -*- coding: utf-8 -*-
"""Mở rộng bộ câu hỏi: 50 tay + 400 sinh từ tiêu đề Điều + 100 tự nhiên (30 cũ + 70 mới) = 550.
Chạy: python eval/expand_questions.py  -> ghi đè golden_questions.json"""
import sys, os, re, json, random
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
import pyarrow.parquet as pq

random.seed(42)
N_GENERATED = 500

KCB = ["15/2023/QH15"]
DUOC = ["105/2016/QH13", "44/2024/QH15", "39/VBHN-VPQH"]
ATTP = ["55/2010/QH12", "61/VBHN-VPQH", "02/VBHN-VPQH"]
BHYT = ["46/2014/QH13", "51/2024/QH15"]
TL = ["09/2012/QH13", "08/VBHN-VPQH", "11/VBHN-VPQH", "15/VBHN-VPQH"]
RB = ["44/2019/QH14"]
HM = ["75/2006/QH11"]
HIV = ["64/2006/QH11", "33/VBHN-VPQH"]
PB = ["114/2025/QH15"]

GROUPS = {
    "KCB": (["15/2023/QH15"], KCB), "Duoc": (["105/2016/QH13", "44/2024/QH15"], DUOC),
    "ATTP": (["55/2010/QH12"], ATTP), "BHYT": (["46/2014/QH13", "51/2024/QH15"], BHYT),
    "ThuocLa": (["09/2012/QH13"], TL), "RuouBia": (["44/2019/QH14"], RB),
    "HienMo": (["75/2006/QH11"], HM), "HIV": (["64/2006/QH11"], HIV),
    "PhongBenh": (["114/2025/QH15"], PB),
}
STOP = ["phạm vi điều chỉnh", "đối tượng áp dụng", "giải thích từ ngữ", "hiệu lực thi hành",
        "tổ chức thực hiện", "quy định chuyển tiếp", "điều khoản thi hành", "sửa đổi",
        "bãi bỏ", "trách nhiệm thi hành", "áp dụng pháp luật", "nguyên tắc"]
RE = re.compile(r"Điều\s+\d+[\.:]?\s+([A-ZÀ-ỸĐ][^\n]{6,110})")

# ---- 70 câu tự nhiên MỚI ----
NATURAL_NEW = [
    # KCB (12)
    ("Bằng bác sĩ học ở nước ngoài về có được hành nghề ở Việt Nam luôn không?", KCB),
    ("Đang cấp cứu mà bệnh viện đòi đóng tiền trước rồi mới chữa, như vậy có đúng không?", KCB),
    ("Bệnh nhân muốn xin bản sao hồ sơ bệnh án của mình thì bệnh viện có phải cung cấp không?", KCB),
    ("Điều dưỡng có được tự ý tiêm thuốc cho bệnh nhân khi chưa có chỉ định của bác sĩ không?", KCB),
    ("Khám chữa bệnh từ xa qua gọi video có hợp pháp không?", KCB),
    ("Bác sĩ bị thu hồi giấy phép hành nghề trong những trường hợp nào?", KCB),
    ("Bệnh viện gây tai biến cho người bệnh do sai sót chuyên môn thì bồi thường thế nào?", KCB),
    ("Muốn chuyển lên bệnh viện tuyến trên điều trị thì cần điều kiện gì?", KCB),
    ("Sinh viên y đang thực tập có được trực tiếp khám cho bệnh nhân không?", KCB),
    ("Lương y có bài thuốc gia truyền có được phép khám chữa bệnh không?", KCB),
    ("Phòng khám có bắt buộc phải niêm yết giá dịch vụ khám chữa bệnh không?", KCB),
    ("Người hành nghề đang bị truy cứu trách nhiệm hình sự có được tiếp tục khám chữa bệnh không?", KCB),
    # Dược (10)
    ("Thuốc kê đơn có được bán cho người không có đơn của bác sĩ không?", DUOC),
    ("Mua bán thuốc qua mạng có hợp pháp không?", DUOC),
    ("Dược sĩ mới ra trường cần thực hành bao lâu mới được đứng tên nhà thuốc?", DUOC),
    ("Nhà thuốc bán thuốc hết hạn sử dụng thì bị xử lý ra sao?", DUOC),
    ("Thuốc xách tay từ nước ngoài về bán có vi phạm pháp luật không?", DUOC),
    ("Giá bán lẻ thuốc do ai quản lý, có được bán cao tùy ý không?", DUOC),
    ("Thuốc đông y, thuốc cổ truyền có phải đăng ký lưu hành không?", DUOC),
    ("Một dược sĩ có được đứng tên chịu trách nhiệm cho hai nhà thuốc cùng lúc không?", DUOC),
    ("Hoạt động giới thiệu thuốc của trình dược viên có bị quản lý không?", DUOC),
    ("Thuốc mới muốn được bán ở Việt Nam phải qua những bước nào?", DUOC),
    # ATTP (9)
    ("Bán đồ ăn vặt trước cổng trường có cần điều kiện gì không?", ATTP),
    ("Thức ăn đường phố được quản lý vệ sinh như thế nào?", ATTP),
    ("Nhà hàng làm khách bị ngộ độc thực phẩm thì bị xử lý sao?", ATTP),
    ("Thực phẩm chức năng quảng cáo như thuốc chữa bệnh có bị cấm không?", ATTP),
    ("Đồ hộp nhập khẩu có phải dán nhãn phụ tiếng Việt không?", ATTP),
    ("Dùng phụ gia, phẩm màu ngoài danh mục cho phép thì bị xử lý thế nào?", ATTP),
    ("Rau quả tồn dư thuốc bảo vệ thực vật vượt ngưỡng có bị cấm bán không?", ATTP),
    ("Cơ sở sản xuất nước uống đóng chai cần đáp ứng điều kiện gì?", ATTP),
    ("Cơ quan nào kiểm tra an toàn thực phẩm ở chợ và siêu thị?", ATTP),
    # BHYT (8)
    ("Mất thẻ bảo hiểm y tế thì xin cấp lại thế nào?", BHYT),
    ("Đi khám trái tuyến thì bảo hiểm y tế chi trả bao nhiêu phần trăm?", BHYT),
    ("Trẻ em dưới 6 tuổi có phải mua thẻ bảo hiểm y tế không?", BHYT),
    ("Hộ nghèo có được nhà nước hỗ trợ tiền đóng bảo hiểm y tế không?", BHYT),
    ("Đi làm ở công ty thì ai phải đóng bảo hiểm y tế, công ty hay người lao động?", BHYT),
    ("Nghỉ việc rồi thì thẻ bảo hiểm y tế còn giá trị sử dụng không?", BHYT),
    ("Khám chữa bệnh ở tỉnh khác nơi đăng ký ban đầu có được hưởng bảo hiểm không?", BHYT),
    ("Bảo hiểm y tế có chi trả cho phẫu thuật thẩm mỹ không?", BHYT),
    # Thuốc lá (7)
    ("Hút thuốc trong quán cà phê trong nhà có vi phạm không?", TL),
    ("Mở đại lý bán buôn thuốc lá cần giấy phép gì?", TL),
    ("Cấm bán thuốc lá gần trường học trong phạm vi bao nhiêu mét?", TL),
    ("Công ty thuốc lá có được tài trợ cho sự kiện văn hóa thể thao không?", TL),
    ("Nơi dành riêng cho người hút thuốc phải đáp ứng điều kiện gì?", TL),
    ("Quỹ phòng chống tác hại thuốc lá lấy nguồn tiền từ đâu?", TL),
    ("Sai trẻ em đi mua thuốc lá hộ có bị cấm không?", TL),
    # Rượu bia (7)
    ("Bán rượu bia qua mạng, qua app giao hàng có được phép không?", RB),
    ("Có khung giờ nào bị cấm bán rượu bia không?", RB),
    ("Ép, khích bác người khác uống rượu có vi phạm pháp luật không?", RB),
    ("Quán nhậu có được bán bia cho người chưa đủ 18 tuổi không?", RB),
    ("Hãng bia tài trợ học bổng cho sinh viên có bị hạn chế gì không?", RB),
    ("Quảng cáo rượu trên 15 độ cồn có bị cấm hoàn toàn không?", RB),
    ("Pháp luật khuyến cáo gì với phụ nữ mang thai về rượu bia?", RB),
    # Hiến mô (6)
    ("Bao nhiêu tuổi thì được đăng ký hiến mô, hiến tạng?", HM),
    ("Hiến tạng có được nhận tiền hay lợi ích vật chất không?", HM),
    ("Người thân có quyền phản đối việc lấy tạng khi người đăng ký hiến đã qua đời không?", HM),
    ("Người hiến thận khi còn sống được hưởng chế độ chăm sóc gì?", HM),
    ("Có được chỉ định hiến tạng cho riêng một người cụ thể không?", HM),
    ("Việc xác định chết não để lấy tạng do ai quyết định, theo tiêu chuẩn nào?", HM),
    # HIV (6)
    ("Khám sức khỏe xin việc có bắt buộc xét nghiệm HIV không?", HIV),
    ("Kết quả xét nghiệm HIV có được giữ bí mật không, ai được biết?", HIV),
    ("Vợ hoặc chồng có quyền được biết bạn đời nhiễm HIV không?", HIV),
    ("Trẻ em nhiễm HIV có được đi học bình thường không?", HIV),
    ("Người biết mình nhiễm HIV mà cố tình lây cho người khác bị xử lý sao?", HIV),
    ("Phụ nữ nhiễm HIV mang thai được hỗ trợ gì để phòng lây truyền sang con?", HIV),
    # Phòng bệnh (5)
    ("Không đưa con đi tiêm chủng bắt buộc thì cha mẹ có vi phạm không?", PB),
    ("Khi có dịch bệnh, cơ quan nhà nước được áp dụng những biện pháp gì?", PB),
    ("Tiêm vắc xin bị tai biến nặng thì có được nhà nước bồi thường không?", PB),
    ("Khám sức khỏe định kỳ được pháp luật quy định thế nào?", PB),
    ("Người từ vùng có dịch trở về có phải khai báo y tế không?", PB),
]


def clean_title(t):
    t = re.split(r"\d", t)[0]
    return t.strip().rstrip(".,;:").strip()


def lower_first(s):
    return s[0].lower() + s[1:] if s else s


def main():
    # 1) tách phần hiện có
    path = os.path.join(HERE, "golden_questions.json")
    cur = json.load(open(path, encoding="utf-8"))
    manual = [q for q in cur if q.get("type") is None][:50]
    natural_old = [q for q in cur if q.get("type") == "natural"]

    # 2) quét tiêu đề Điều
    scan = {dn: name for name, (scans, _) in GROUPS.items() for dn in scans}
    titles = {name: set() for name in GROUPS}
    pf = pq.ParquetFile("legal_medical_chunks_clean.parquet")
    for b in pf.iter_batches(columns=["document_number", "text"]):
        d = b.to_pydict()
        for dn, t in zip(d["document_number"], d["text"]):
            g = scan.get(dn)
            if not g:
                continue
            for m in RE.findall(t):
                ti = clean_title(m)
                low = ti.lower()
                if len(ti) < 10 or ti.isupper() or any(s in low for s in STOP):
                    continue
                titles[g].add(ti)
    for g in titles:
        titles[g] = sorted(titles[g]); random.shuffle(titles[g])

    # 3) sinh 400 câu
    seen = {q["q"].strip().lower() for q in manual}
    templates = [lambda t: f"Pháp luật quy định như thế nào về {lower_first(t)}?",
                 lambda t: f"{t} được quy định ra sao?",
                 lambda t: f"Nội dung quy định về {lower_first(t)} là gì?"]
    generated = []
    names = list(GROUPS)
    # tối đa 3 vòng: mỗi vòng đi hết các tiêu đề với MỘT template khác nhau
    for round_i in range(3):
        if len(generated) >= N_GENERATED:
            break
        idx = {g: 0 for g in GROUPS}; ti = round_i  # lệch template theo vòng
        exhausted = False
        while len(generated) < N_GENERATED and not exhausted:
            progressed = False
            for g in names:
                if len(generated) >= N_GENERATED:
                    break
                lst = titles[g]
                while idx[g] < len(lst):
                    title = lst[idx[g]]; idx[g] += 1
                    q = templates[(ti + round_i) % 3](title); ti += 1
                    if q.strip().lower() in seen:
                        continue
                    seen.add(q.strip().lower())
                    generated.append({"q": q, "relevant": GROUPS[g][1], "type": "generated"})
                    progressed = True
                    break
            if not progressed:
                exhausted = True

    # 4) câu tự nhiên: cũ + mới
    nat = list(natural_old)
    nseen = {q["q"].strip().lower() for q in nat}
    for q, rel in NATURAL_NEW:
        if q.strip().lower() in nseen:
            continue
        nat.append({"q": q, "relevant": rel, "type": "natural"})
        nseen.add(q.strip().lower())

    out = manual + generated + nat
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Tổng: {len(out)} = tay {len(manual)} + sinh {len(generated)} + tự nhiên {len(nat)}")
    print("Tiêu đề khả dụng:", {g: len(titles[g]) for g in GROUPS})


if __name__ == "__main__":
    main()
