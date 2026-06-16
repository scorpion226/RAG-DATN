# -*- coding: utf-8 -*-
"""
query_expand.py — Mở rộng truy vấn bằng TỪ ĐIỂN ÁNH XẠ thuật ngữ đời thường -> pháp lý.

Động cơ: câu hỏi của người dân dùng ngôn ngữ đời thường ("mở quán ăn nhỏ", "quầy thuốc
ở quê") trong khi văn bản pháp luật dùng thuật ngữ chuẩn ("cơ sở kinh doanh dịch vụ ăn
uống", "cơ sở bán lẻ thuốc"). Khoảng cách từ vựng (lexical gap) này làm cả bi-encoder lẫn
BM25 trượt (xem Thí nghiệm 5). Thí nghiệm 6 cho thấy viết lại bằng LLM 4B KHÔNG ổn định
(bịa trích dẫn, không tuân chỉ dẫn). Giải pháp ở đây là một TỪ ĐIỂN KIỂM SOÁT TỪ VỰNG
(controlled-vocabulary query expansion) — xác định, rẻ, không phụ thuộc độ tin cậy LLM.

Cách dùng: nếu câu hỏi chứa cụm đời thường (trigger), NỐI THÊM cụm thuật ngữ pháp lý
tương ứng vào câu hỏi trước khi truy xuất (không thay thế — giữ nguyên tín hiệu gốc).

Từ điển được xây theo 8 lĩnh vực luật y tế trong corpus, dựa trên THUẬT NGỮ chuẩn của
văn bản (không gắn với số hiệu hay đáp án cụ thể), nên tổng quát hóa được sang câu mới.
"""

# Mỗi mục: (danh sách cụm đời thường kích hoạt, cụm thuật ngữ pháp lý nối thêm)
# Trigger so khớp ở dạng chữ thường, không phân biệt hoa thường.
TERM_MAP = [
    # ===== Khám bệnh, chữa bệnh =====
    (["mở phòng khám", "phòng khám tư", "mở cửa hoạt động", "mở bệnh viện", "cơ sở khám"],
     "giấy phép hoạt động cơ sở khám bệnh chữa bệnh điều kiện"),
    (["đi làm khám", "hành nghề", "được khám chữa bệnh", "đi làm khám chữa bệnh",
      "tốt nghiệp bác sĩ", "được làm bác sĩ"],
     "giấy phép hành nghề khám bệnh chữa bệnh điều kiện cấp"),
    (["bác sĩ nước ngoài", "người nước ngoài", "học ở nước ngoài", "bằng nước ngoài",
      "ở nước ngoài về"],
     "người nước ngoài hành nghề khám bệnh chữa bệnh ngôn ngữ công nhận văn bằng"),
    (["từ chối chữa", "từ chối khám", "không chữa cho"],
     "quyền và nghĩa vụ của người hành nghề từ chối khám bệnh chữa bệnh"),
    (["khiếu nại", "không hài lòng", "yêu cầu gì"],
     "quyền của người bệnh khiếu nại"),
    (["hồ sơ bệnh án", "bệnh án", "bản sao hồ sơ"],
     "hồ sơ bệnh án quyền được cung cấp thông tin của người bệnh"),
    (["cấp cứu", "đóng tiền trước", "đòi tiền trước"],
     "cấp cứu trách nhiệm của cơ sở khám bệnh chữa bệnh"),
    (["thu hồi giấy phép", "tước giấy phép", "bị thu hồi"],
     "thu hồi giấy phép hành nghề đình chỉ"),
    (["tai biến", "sai sót chuyên môn", "bồi thường"],
     "sai sót chuyên môn kỹ thuật tai biến y khoa bồi thường"),
    (["khám từ xa", "gọi video", "khám online", "telehealth"],
     "khám bệnh chữa bệnh từ xa"),
    (["điều dưỡng", "y tá", "tự ý tiêm"],
     "phạm vi hành nghề chỉ định của người hành nghề"),
    (["thực tập", "sinh viên y", "thực hành"],
     "thực hành khám bệnh chữa bệnh người học"),
    (["lương y", "bài thuốc gia truyền", "gia truyền"],
     "lương y người có bài thuốc gia truyền khám bệnh chữa bệnh y học cổ truyền"),
    (["niêm yết giá", "công khai giá"],
     "giá dịch vụ khám bệnh chữa bệnh niêm yết"),
    (["truy cứu trách nhiệm hình sự", "đang bị truy tố"],
     "các trường hợp bị cấm hành nghề khám bệnh chữa bệnh"),
    (["chuyển tuyến", "tuyến trên", "chuyển lên bệnh viện", "chuyển viện"],
     "chuyển người bệnh giữa các cơ sở khám bệnh chữa bệnh cấp chuyên môn"),
    (["khám sức khỏe định kỳ", "khám sức khỏe xin việc", "khám sức khỏe"],
     "khám sức khỏe khám bệnh nghề nghiệp"),

    # ===== Dược =====
    (["quầy thuốc", "nhà thuốc", "hiệu thuốc", "cơ sở bán thuốc", "bán lẻ thuốc"],
     "cơ sở bán lẻ thuốc điều kiện kinh doanh dược"),
    (["đứng tên", "chịu trách nhiệm chuyên môn", "đứng tên nhà thuốc"],
     "người chịu trách nhiệm chuyên môn về dược chứng chỉ hành nghề dược"),
    (["dược sĩ mới ra trường", "thực hành bao lâu", "thời gian thực hành dược"],
     "điều kiện cấp chứng chỉ hành nghề dược thực hành chuyên môn"),
    (["thuốc giả", "thuốc kém chất lượng", "thuốc hết hạn", "thuốc không đạt"],
     "thuốc giả thuốc không đạt tiêu chuẩn chất lượng hành vi bị nghiêm cấm trong hoạt động dược"),
    (["quảng cáo thuốc"],
     "thông tin quảng cáo thuốc"),
    (["bán thuốc qua mạng", "mua bán thuốc qua mạng", "thuốc qua mạng", "thuốc online"],
     "kinh doanh thuốc theo phương thức thương mại điện tử"),
    (["thuốc kê đơn", "không có đơn", "bán theo đơn"],
     "thuốc kê đơn bán thuốc theo đơn"),
    (["thuốc đông y", "thuốc cổ truyền", "thuốc nam", "thuốc bắc"],
     "thuốc cổ truyền đăng ký lưu hành thuốc"),
    (["thuốc xách tay", "thuốc nhập từ nước ngoài", "thuốc nhập khẩu"],
     "nhập khẩu thuốc đăng ký lưu hành"),
    (["giá thuốc", "tăng giá thuốc", "giá bán lẻ thuốc", "bán cao"],
     "quản lý giá thuốc kê khai giá"),
    (["trình dược viên", "giới thiệu thuốc"],
     "thông tin thuốc người giới thiệu thuốc"),
    (["thuốc mới", "đưa thuốc ra thị trường", "lưu hành thuốc"],
     "đăng ký lưu hành thuốc thử thuốc trên lâm sàng"),
    (["hai nhà thuốc", "hai cơ sở", "cùng lúc"],
     "một chứng chỉ hành nghề dược một cơ sở"),

    # ===== An toàn thực phẩm =====
    (["quán ăn", "nhà hàng", "quán nhậu", "dịch vụ ăn uống", "đồ ăn vặt", "bán đồ ăn"],
     "cơ sở kinh doanh dịch vụ ăn uống giấy chứng nhận cơ sở đủ điều kiện an toàn thực phẩm"),
    (["thức ăn đường phố", "bán hàng rong", "trước cổng trường"],
     "thức ăn đường phố điều kiện bảo đảm an toàn thực phẩm"),
    (["ngộ độc thực phẩm", "ngộ độc"],
     "ngộ độc thực phẩm phòng ngừa khắc phục sự cố an toàn thực phẩm"),
    (["thực phẩm chức năng", "quảng cáo như thuốc"],
     "thực phẩm chức năng quảng cáo thực phẩm"),
    (["nhãn", "bao bì", "dán nhãn", "ghi trên bao"],
     "ghi nhãn thực phẩm nhãn phụ tiếng Việt"),
    (["phụ gia", "phẩm màu", "chất bảo quản"],
     "phụ gia thực phẩm danh mục được phép sử dụng"),
    (["thuốc bảo vệ thực vật", "tồn dư", "dư lượng", "rau quả tươi", "rau quả"],
     "an toàn thực phẩm giới hạn dư lượng điều kiện bảo đảm an toàn"),
    (["nước uống đóng chai", "cơ sở sản xuất", "sản xuất thực phẩm"],
     "điều kiện bảo đảm an toàn thực phẩm cơ sở sản xuất"),
    (["hàng xách tay", "đồ ăn nhập", "thực phẩm nhập khẩu", "đồ hộp nhập"],
     "kiểm tra nhà nước về an toàn thực phẩm nhập khẩu"),
    (["cơ quan nào kiểm tra", "ai kiểm tra", "quản lý an toàn thực phẩm"],
     "trách nhiệm quản lý nhà nước về an toàn thực phẩm thanh tra kiểm tra"),

    # ===== Bảo hiểm y tế =====
    (["bảo hiểm y tế", "bhyt", "thẻ bảo hiểm", "thẻ bhyt"],
     "bảo hiểm y tế mức hưởng phạm vi được hưởng"),
    (["đóng bao nhiêu", "mức đóng", "ai trả", "tiền đóng"],
     "mức đóng trách nhiệm đóng bảo hiểm y tế"),
    (["trái tuyến", "đúng tuyến", "tỉnh khác", "nơi đăng ký ban đầu"],
     "khám bệnh chữa bệnh bảo hiểm y tế đúng tuyến trái tuyến thông tuyến"),
    (["không chi trả", "không thanh toán", "không được hưởng"],
     "các trường hợp không được hưởng bảo hiểm y tế"),
    (["mất thẻ", "cấp lại thẻ"],
     "cấp lại đổi thẻ bảo hiểm y tế"),
    (["dưới 6 tuổi", "trẻ em dưới"],
     "đối tượng tham gia bảo hiểm y tế trẻ em dưới 6 tuổi"),
    (["hộ nghèo", "hỗ trợ tiền đóng", "nhà nước hỗ trợ"],
     "đối tượng được ngân sách nhà nước hỗ trợ đóng bảo hiểm y tế"),
    (["sinh viên", "học sinh"],
     "đối tượng tham gia bảo hiểm y tế học sinh sinh viên"),
    (["nghỉ việc", "còn giá trị"],
     "thời hạn giá trị sử dụng thẻ bảo hiểm y tế"),
    (["phẫu thuật thẩm mỹ", "thẩm mỹ"],
     "các trường hợp không được hưởng bảo hiểm y tế thẩm mỹ"),

    # ===== Phòng chống tác hại thuốc lá =====
    (["hút thuốc", "thuốc lá"],
     "phòng chống tác hại của thuốc lá địa điểm cấm hút thuốc lá"),
    (["vỏ bao thuốc", "cảnh báo", "in hình"],
     "ghi nhãn in cảnh báo sức khỏe trên bao bì thuốc lá"),
    (["bán thuốc lá cho trẻ", "trẻ em dưới 18", "cho người chưa đủ 18"],
     "hành vi bị nghiêm cấm bán thuốc lá cho người chưa đủ 18 tuổi"),
    (["đại lý", "bán buôn thuốc lá", "giấy phép thuốc lá"],
     "kinh doanh thuốc lá giấy phép"),
    (["gần trường học", "phạm vi bao nhiêu mét", "cấm bán gần"],
     "địa điểm cấm bán thuốc lá"),
    (["tài trợ", "sự kiện văn hóa"],
     "cấm quảng cáo khuyến mại tài trợ thuốc lá"),
    (["nơi dành riêng", "phòng hút thuốc"],
     "địa điểm cấm hút thuốc lá nơi dành riêng cho người hút thuốc"),
    (["quỹ phòng chống", "nguồn tiền"],
     "Quỹ phòng chống tác hại của thuốc lá"),

    # ===== Phòng chống tác hại rượu bia =====
    (["uống bia", "uống rượu", "rượu bia", "lái xe", "nồng độ cồn"],
     "phòng chống tác hại của rượu bia hành vi bị nghiêm cấm điều khiển phương tiện"),
    (["bán rượu cho", "bán bia cho", "chưa đủ 18", "học sinh"],
     "hành vi bị nghiêm cấm bán rượu bia cho người chưa đủ 18 tuổi"),
    (["quảng cáo bia", "quảng cáo rượu", "giờ vàng"],
     "quản lý quảng cáo rượu bia"),
    (["bán rượu qua mạng", "app giao hàng", "bán bia qua mạng"],
     "điều kiện bán rượu bia theo hình thức thương mại điện tử"),
    (["khung giờ", "cấm bán rượu"],
     "địa điểm thời gian không được bán rượu bia"),
    (["ép", "khích bác", "ép uống"],
     "hành vi bị nghiêm cấm xúi giục ép buộc uống rượu bia"),
    (["tài trợ học bổng", "hãng bia tài trợ"],
     "hạn chế quảng cáo tài trợ rượu bia"),
    (["phụ nữ mang thai", "bà bầu"],
     "phòng chống tác hại rượu bia phụ nữ mang thai"),

    # ===== Hiến, lấy, ghép mô, tạng =====
    (["hiến tạng", "hiến mô", "hiến thận", "hiến gan", "đăng ký hiến"],
     "hiến lấy ghép mô bộ phận cơ thể người điều kiện thủ tục đăng ký"),
    (["mua bán thận", "mua bán tạng", "bán nội tạng"],
     "hành vi bị nghiêm cấm mua bán mô bộ phận cơ thể người"),
    (["bao nhiêu tuổi", "đủ tuổi hiến"],
     "điều kiện độ tuổi đăng ký hiến mô bộ phận cơ thể người"),
    (["nhận tiền", "lợi ích vật chất"],
     "nguyên tắc tự nguyện không vì mục đích thương mại hiến mô tạng"),
    (["người thân phản đối", "gia đình phản đối"],
     "lấy mô bộ phận cơ thể ở người sau khi chết"),
    (["chăm sóc", "chế độ", "người hiến thận"],
     "chế độ chăm sóc sức khỏe đối với người đã hiến mô bộ phận cơ thể"),
    (["chỉ định hiến", "cho riêng một người"],
     "điều phối hiến ghép mô bộ phận cơ thể người"),
    (["chết não", "xác định chết"],
     "tiêu chuẩn điều kiện xác định chết não"),

    # ===== HIV/AIDS =====
    (["nhiễm hiv", "người hiv", "hiv"],
     "phòng chống HIV/AIDS quyền nghĩa vụ của người nhiễm HIV"),
    (["đuổi việc", "đuổi học", "phân biệt đối xử", "kỳ thị"],
     "hành vi bị nghiêm cấm phân biệt đối xử với người nhiễm HIV"),
    (["xét nghiệm hiv", "tuyển dụng", "xin việc"],
     "hành vi bị nghiêm cấm yêu cầu xét nghiệm HIV khi tuyển dụng"),
    (["giữ bí mật", "kết quả xét nghiệm", "ai được biết"],
     "thông báo kết quả xét nghiệm HIV bảo mật thông tin"),
    (["cố tình lây", "lây cho người khác"],
     "hành vi bị nghiêm cấm cố ý lây truyền HIV"),
    (["mang thai", "lây truyền sang con", "mẹ sang con"],
     "dự phòng lây truyền HIV từ mẹ sang con"),
    (["đi học bình thường", "trẻ em nhiễm"],
     "quyền của trẻ em người nhiễm HIV học tập"),

    # ===== Phòng bệnh, tiêm chủng, dịch =====
    (["tiêm vắc xin", "tiêm chủng", "vắc xin", "tiêm phòng"],
     "sử dụng vắc xin tiêm chủng mở rộng phòng chống bệnh truyền nhiễm"),
    (["tai biến tiêm", "tai biến vắc xin", "phản ứng sau tiêm"],
     "bồi thường khi sử dụng vắc xin tai biến nặng"),
    (["dịch bệnh", "có dịch", "chống dịch"],
     "phòng chống bệnh truyền nhiễm công bố dịch biện pháp chống dịch"),
    (["khai báo y tế", "vùng có dịch", "từ vùng dịch"],
     "kiểm dịch y tế khai báo y tế biên giới"),
    (["bắt buộc tiêm", "không đưa con đi tiêm"],
     "tiêm chủng bắt buộc trách nhiệm phòng bệnh"),

    # ===== Bổ sung (phủ các chủ đề đời thường đa dạng hơn) =====
    # KCB
    (["đổi bác sĩ", "yêu cầu đổi", "bác sĩ khác"],
     "quyền lựa chọn của người bệnh trong khám bệnh chữa bệnh"),
    (["quay phim", "chụp ảnh bệnh nhân", "đọc bệnh án", "xem bệnh án"],
     "quyền được tôn trọng bí mật riêng tư hồ sơ bệnh án của người bệnh"),
    (["nhận quà", "phong bì", "nhận tiền của bệnh nhân"],
     "những hành vi bị nghiêm cấm trong khám bệnh chữa bệnh"),
    (["vào phòng mổ", "trước khi phẫu thuật", "đồng ý phẫu thuật"],
     "sự đồng ý của người bệnh quyền của người bệnh khám bệnh chữa bệnh"),
    (["mở bệnh viện", "bệnh viện tư nhân"],
     "giấy phép hoạt động cơ sở khám bệnh chữa bệnh hình thức tổ chức"),
    # Dược
    (["kháng sinh", "thuốc tránh thai", "thuốc cảm", "không kê đơn"],
     "thuốc kê đơn thuốc không kê đơn bán thuốc theo đơn"),
    (["pha chế thuốc", "tự pha chế"],
     "pha chế thuốc tại cơ sở bán lẻ điều kiện kinh doanh dược"),
    (["thuốc gây nghiện", "thuốc hướng thần"],
     "thuốc phải kiểm soát đặc biệt thuốc gây nghiện hướng thần"),
    (["thuốc hiếm", "thuốc chưa có ở việt nam"],
     "nhập khẩu thuốc chưa có giấy đăng ký lưu hành"),
    (["thuê dược sĩ", "không học dược"],
     "điều kiện cấp giấy chứng nhận đủ điều kiện kinh doanh dược người chịu trách nhiệm chuyên môn"),
    # ATTP
    (["trà sữa", "đồ uống", "quán cà phê bán đồ ăn"],
     "cơ sở kinh doanh dịch vụ ăn uống điều kiện bảo đảm an toàn thực phẩm"),
    (["bếp ăn tập thể", "căng tin", "suất ăn"],
     "điều kiện bảo đảm an toàn thực phẩm bếp ăn tập thể kinh doanh dịch vụ ăn uống"),
    (["giò chả", "cơ sở sản xuất thực phẩm", "làm bánh"],
     "điều kiện bảo đảm an toàn thực phẩm cơ sở sản xuất thực phẩm"),
    (["nước đá", "đá viên"],
     "điều kiện bảo đảm an toàn thực phẩm sản xuất"),
    (["thịt heo", "dấu kiểm dịch", "hải sản tươi"],
     "điều kiện bảo đảm an toàn thực phẩm bảo quản kinh doanh thực phẩm tươi sống"),
    (["người bán hàng ăn", "khám sức khỏe người chế biến"],
     "điều kiện đối với người trực tiếp sản xuất kinh doanh thực phẩm"),
    # BHYT
    (["sinh con", "thai sản", "đẻ"],
     "phạm vi được hưởng bảo hiểm y tế khám chữa bệnh"),
    (["khám răng", "làm răng", "nha khoa"],
     "phạm vi được hưởng và mức hưởng bảo hiểm y tế"),
    (["tai nạn giao thông"],
     "phạm vi được hưởng bảo hiểm y tế các trường hợp"),
    (["bao lâu mới được dùng thẻ", "thẻ có giá trị từ khi nào"],
     "thời điểm thẻ bảo hiểm y tế có giá trị sử dụng"),
    (["trên 80 tuổi", "người cao tuổi", "người già"],
     "đối tượng tham gia bảo hiểm y tế được ngân sách nhà nước đóng"),
    # Thuốc lá
    (["thuốc lá điện tử", "thuốc lá nung nóng", "vape"],
     "sản phẩm thuốc lá tác hại của thuốc lá hành vi bị nghiêm cấm"),
    (["karaoke", "quán bar", "vũ trường", "quán cà phê trong nhà"],
     "địa điểm cấm hút thuốc lá hoàn toàn trong nhà"),
    (["bán lẻ từng điếu", "bán thuốc lá lẻ"],
     "hành vi bị nghiêm cấm kinh doanh thuốc lá"),
    (["cơ quan", "công sở", "nơi làm việc"],
     "địa điểm cấm hút thuốc lá"),
    # Rượu bia
    (["người say", "đã say xỉn"],
     "hành vi bị nghiêm cấm bán rượu bia"),
    (["rượu tự nấu", "nấu rượu", "rượu thủ công"],
     "sản xuất rượu thủ công quản lý cung cấp rượu bia"),
    (["trong giờ làm việc", "uống rượu ở cơ quan"],
     "hành vi bị nghiêm cấm uống rượu bia tại nơi làm việc"),
    (["bệnh viện trường học", "địa điểm không được bán"],
     "địa điểm không được bán rượu bia"),
    # Hiến mô tạng
    (["hiến giác mạc", "hiến tủy", "hiến xác", "hiến mắt"],
     "hiến mô bộ phận cơ thể người hiến xác đăng ký"),
    (["rút lại đăng ký hiến", "đổi ý"],
     "đăng ký hiến thay đổi rút đăng ký hiến mô bộ phận cơ thể"),
    (["bệnh viện nào được ghép", "cơ sở ghép tạng"],
     "điều kiện cơ sở y tế lấy ghép mô bộ phận cơ thể người"),
    (["chọn người nhận", "chỉ định người nhận"],
     "điều phối lấy ghép mô bộ phận cơ thể người"),
    # HIV
    (["kim tiêm đâm", "phơi nhiễm", "sợ lây hiv"],
     "dự phòng sau phơi nhiễm với HIV"),
    (["thuốc điều trị hiv", "thuốc arv", "miễn phí hiv"],
     "điều trị bằng thuốc kháng HIV tiếp cận điều trị"),
    (["kết hôn", "sinh con", "người nhiễm hiv lấy"],
     "quyền và nghĩa vụ của người nhiễm HIV"),
    (["nghĩa vụ quân sự", "đi học", "đi làm hiv"],
     "không phân biệt đối xử quyền của người nhiễm HIV"),
    (["cơ sở cai nghiện", "bắt buộc xét nghiệm"],
     "xét nghiệm HIV tự nguyện bắt buộc các trường hợp"),
    # Phòng bệnh, dịch
    (["sốc phản vệ", "tai biến sau tiêm", "phản ứng sau tiêm"],
     "bồi thường tai biến nặng sau tiêm chủng sử dụng vắc xin"),
    (["phong tỏa", "giãn cách", "cách ly khu dân cư"],
     "biện pháp chống dịch vùng có dịch ban bố tình trạng khẩn cấp"),
    (["cách ly", "cách ly y tế"],
     "cách ly y tế cưỡng chế cách ly biện pháp phòng chống bệnh truyền nhiễm"),
    (["bệnh truyền nhiễm nhóm", "nhóm a nhóm b"],
     "phân loại bệnh truyền nhiễm danh mục nhóm A B C"),
    (["chống đối cách ly", "trốn cách ly", "trốn khai báo"],
     "hành vi bị nghiêm cấm trong phòng chống bệnh truyền nhiễm"),
    (["diệt muỗi", "sốt xuất huyết", "phun thuốc"],
     "biện pháp phòng bệnh truyền nhiễm trách nhiệm phòng chống dịch"),
    (["nhập cảnh", "kiểm dịch biên giới"],
     "kiểm dịch y tế biên giới"),
]


def expand_query(q, max_terms=4):
    """Trả về câu hỏi đã NỐI THÊM thuật ngữ pháp lý (nếu khớp trigger).
    max_terms: giới hạn số cụm thuật ngữ nối thêm để tránh loãng truy vấn."""
    ql = q.lower()
    added, seen = [], set()
    for triggers, expansion in TERM_MAP:
        if any(t in ql for t in triggers):
            if expansion not in seen:
                added.append(expansion)
                seen.add(expansion)
        if len(added) >= max_terms:
            break
    if not added:
        return q
    return q + " " + " ".join(added)


def convert_query(q, max_terms=4):
    """CHUYỂN ĐỔI: thay cụm đời thường BẰNG thuật ngữ pháp lý (không giữ cụm gốc).
    Khác expand_query (nối thêm) — đây là phép chuyển ngôn ngữ đời thường -> pháp lý."""
    out = q
    n = 0
    for triggers, expansion in TERM_MAP:
        for t in triggers:
            idx = out.lower().find(t)
            if idx >= 0:
                out = out[:idx] + expansion + out[idx + len(t):]
                n += 1
                break
        if n >= max_terms:
            break
    return out


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    tests = [
        "Mở quán ăn nhỏ có cần xin giấy chứng nhận vệ sinh an toàn thực phẩm không?",
        "Tôi muốn mở quầy thuốc ở quê thì cần bằng cấp và điều kiện gì?",
        "Bác sĩ nước ngoài sang Việt Nam làm việc có cần biết tiếng Việt không?",
        "Uống bia rồi lái xe máy về nhà có vi phạm pháp luật không?",
    ]
    for t in tests:
        print("IN :", t)
        print("OUT:", expand_query(t))
        print()
