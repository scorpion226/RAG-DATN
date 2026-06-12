# -*- coding: utf-8 -*-
"""Mở rộng bộ câu hỏi vàng lên 200 câu: giữ các câu tự viết, sinh thêm câu neo vào
TIÊU ĐỀ ĐIỀU thật trong từng luật (ground-truth = số hiệu luật + VBHN tương đương).
Chạy: python eval/generate_questions.py  -> ghi đè golden_questions.json (200 câu)."""
import sys, os, re, json, random
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
import pyarrow.parquet as pq

random.seed(42)
TARGET = 200

# group: (tập số hiệu để quét tiêu đề Điều, ground-truth)
GROUPS = {
    "KCB":      (["15/2023/QH15"], ["15/2023/QH15"]),
    "Duoc":     (["105/2016/QH13", "44/2024/QH15"], ["105/2016/QH13", "44/2024/QH15", "39/VBHN-VPQH"]),
    "ATTP":     (["55/2010/QH12"], ["55/2010/QH12", "61/VBHN-VPQH", "02/VBHN-VPQH"]),
    "BHYT":     (["46/2014/QH13", "51/2024/QH15"], ["46/2014/QH13", "51/2024/QH15"]),
    "ThuocLa":  (["09/2012/QH13"], ["09/2012/QH13", "08/VBHN-VPQH", "11/VBHN-VPQH", "15/VBHN-VPQH"]),
    "RuouBia":  (["44/2019/QH14"], ["44/2019/QH14"]),
    "HienMo":   (["75/2006/QH11"], ["75/2006/QH11"]),
    "HIV":      (["64/2006/QH11"], ["64/2006/QH11", "33/VBHN-VPQH"]),
    "PhongBenh":(["114/2025/QH15"], ["114/2025/QH15"]),
}
# tiêu đề Điều chung chung (xuất hiện ở mọi luật) -> loại để câu hỏi có tính phân biệt
STOP = ["phạm vi điều chỉnh", "đối tượng áp dụng", "giải thích từ ngữ", "hiệu lực thi hành",
        "tổ chức thực hiện", "quy định chuyển tiếp", "điều khoản thi hành", "sửa đổi",
        "bãi bỏ", "trách nhiệm thi hành", "áp dụng pháp luật", "nguyên tắc"]
RE = re.compile(r"Điều\s+\d+[\.:]?\s+([A-ZÀ-ỸĐ][^\n]{6,110})")


def clean_title(t):
    t = re.split(r"\d", t)[0]                  # cắt tại chữ số (thường bắt đầu khoản "1.")
    t = t.strip().rstrip(".,;:").strip()
    return t


def lower_first(s):
    return s[0].lower() + s[1:] if s else s


def main():
    # 1) thu tiêu đề Điều theo group
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
                if len(ti) < 10 or ti.isupper():
                    continue
                if any(s in low for s in STOP):
                    continue
                titles[g].add(ti)
    for g in titles:
        titles[g] = sorted(titles[g])
        random.shuffle(titles[g])

    # 2) giữ câu tự viết sẵn có
    existing = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
    seen_q = {q["q"].strip().lower() for q in existing}
    out = list(existing)

    # 3) sinh thêm theo round-robin tới khi đủ TARGET
    templates = [lambda t: f"Pháp luật quy định như thế nào về {lower_first(t)}?",
                 lambda t: f"{t} được quy định ra sao?",
                 lambda t: f"Nội dung quy định về {lower_first(t)} là gì?"]
    idx = {g: 0 for g in GROUPS}
    names = list(GROUPS)
    ti = 0
    while len(out) < TARGET:
        progressed = False
        for g in names:
            if len(out) >= TARGET:
                break
            lst = titles[g]
            while idx[g] < len(lst):
                title = lst[idx[g]]; idx[g] += 1
                q = templates[ti % len(templates)](title); ti += 1
                if q.strip().lower() in seen_q:
                    continue
                seen_q.add(q.strip().lower())
                out.append({"q": q, "relevant": GROUPS[g][1]})
                progressed = True
                break
        if not progressed:
            break

    json.dump(out, open(os.path.join(HERE, "golden_questions.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    import statistics
    print(f"Tổng câu hỏi: {len(out)} (tự viết {len(existing)} + sinh {len(out)-len(existing)})")
    print("Tiêu đề Điều khả dụng/group:", {g: len(titles[g]) for g in GROUPS})
    print("|relevant| TB:", round(statistics.mean(len(q['relevant']) for q in out), 2))


if __name__ == "__main__":
    main()
