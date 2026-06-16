# -*- coding: utf-8 -*-
"""#1 — Khai thác bán tự động mục "Giải thích từ ngữ" trong các luật để mở rộng từ điển.
Trích các cặp (thuật ngữ pháp lý, từ khóa trong định nghĩa) -> mined_terms.json.
Ý tưởng: nếu câu hỏi chứa từ khóa mô tả (trong định nghĩa), nối thêm chính THUẬT NGỮ pháp lý.
Chạy: python eval/mine_glossary.py"""
import os, re, json, sys
sys.stdout.reconfigure(encoding="utf-8")
import pyarrow.parquet as pq

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PARQUET = os.path.join(ROOT, "legal_medical_chunks_clean.parquet")
LAWS = {"15/2023/QH15", "105/2016/QH13", "44/2024/QH15", "55/2010/QH12", "46/2014/QH13",
        "51/2024/QH15", "09/2012/QH13", "44/2019/QH14", "75/2006/QH11", "64/2006/QH11",
        "114/2025/QH15"}
# "1. <Thuật ngữ> là <định nghĩa>"  (số có thể dính ký tự trước: "phẩm.2. Bia là...")
DEFRE = re.compile(r"\b(\d{1,2})\.\s*([A-ZÀ-ỸĐ][^\d\n]{2,55}?)\s+(?:là|được hiểu là)\s+(.{15,350}?)(?=\b\d{1,2}\.\s*[A-ZÀ-ỸĐ]|\Z)", re.S)
STOPW = set("là và của các một trong được người khi cho về theo hoặc đối với những tại có thể mà thì này đó nhằm cũng đã sẽ bị do từ nếu để trên dưới sau trước".split())


def keywords(text, k=6):
    """Lấy các từ nội dung (>3 ký tự, không stopword) làm 'cue' đời thường."""
    words = re.findall(r"[a-zà-ỹđA-ZÀ-ỸĐ]{4,}", text.lower())
    seen, out = set(), []
    for w in words:
        if w in STOPW or w in seen:
            continue
        seen.add(w); out.append(w)
        if len(out) >= k:
            break
    return out


def main():
    # gom toàn bộ chunk của mỗi luật, sắp theo chunk_id, ghép rồi cắt vùng "Giải thích từ ngữ"
    law_chunks = {dn: [] for dn in LAWS}
    pf = pq.ParquetFile(PARQUET)
    for b in pf.iter_batches(columns=["document_number", "text", "chunk_id"], batch_size=8000):
        d = b.to_pydict()
        for dn, t, cid in zip(d["document_number"], d["text"], d["chunk_id"]):
            if dn in law_chunks:
                law_chunks[dn].append((cid, t))
    glossary_text = {}
    for dn, chs in law_chunks.items():
        if not chs:
            continue
        chs.sort()
        full = " ".join(t for _, t in chs[:6])     # Điều 1-3 thường nằm ở đầu
        low = full.lower()
        i = low.find("giải thích từ ngữ")
        if i >= 0:
            glossary_text[dn] = full[i:i + 6000]
    mined = []
    for dn, txt in glossary_text.items():
        for m in DEFRE.finditer(txt):
            term = re.sub(r"\s+", " ", m.group(2)).strip().strip(",;")
            defi = m.group(3).strip()
            if 4 <= len(term) <= 60 and not term.isupper():
                mined.append({"law": dn, "term": term.lower(), "cues": keywords(defi)})
    # khử trùng theo term
    uniq = {}
    for e in mined:
        uniq.setdefault(e["term"], e)
    out = list(uniq.values())
    json.dump(out, open(os.path.join(HERE, "mined_terms.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"Trích {len(out)} thuật ngữ từ {len(glossary_text)} luật có mục Giải thích từ ngữ")
    for e in out[:15]:
        print(f"  [{e['law']}] {e['term']}  <- cues: {', '.join(e['cues'])}")
    print("✅ Lưu eval/mined_terms.json")


if __name__ == "__main__":
    main()
