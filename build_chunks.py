"""
build_chunks.py — Pipeline NẠP DỮ LIỆU sạch cho hệ thống RAG (DATN).

Sửa 2 bug của filter_medical_data.py cũ:
  (1) mất ~75% văn bản, (2) ghi lặp ~78 lần.

Cải tiến (kèm lý do để đưa vào báo cáo):
  - Giữ dấu / - ( ) % . , khi làm sạch  -> bảo toàn số hiệu VB (vd 147/2025/NĐ-CP)
  - Thêm cột document_number (số hiệu chính thức từ metadata) -> trích dẫn chính xác
  - Chunk theo đơn vị ngữ nghĩa pháp luật ("Điều", "Chương") ~1200 ký tự, overlap 150
  - Lọc effect_status = "In effect" -> chatbot chỉ tư vấn VB còn hiệu lực
  - Khử trùng lặp chunk (hash) -> loại boilerplate lặp

Chạy: python build_chunks.py
Đầu ra: legal_medical_chunks_clean.parquet
"""
import sys, os, re, hashlib
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import pyarrow.parquet as pq
import pyarrow as pa
from tqdm import tqdm

# ---- Cấu hình ----
HF_SNAPSHOT = (r"C:\Users\admin/.cache/huggingface/hub/"
               r"datasets--th1nhng0--vietnamese-legal-documents/snapshots/"
               r"0a39ad7eae8e6c188cb225c4b1443c3b346461d8/legacy")
META_PATH = HF_SNAPSHOT + r"/metadata.parquet"
CONTENT_PATH = HF_SNAPSHOT + r"/content.parquet"
OUT_PARQUET = "legal_medical_chunks_clean.parquet"

SECTOR_PATTERN = r"Health|Y tế"
KEEP_STATUSES = {"In effect"}      # lọc hiệu lực; để None nếu muốn giữ tất cả
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
MIN_CHUNK_LEN = 80                  # bỏ chunk quá ngắn (vô nghĩa)
FLUSH_EVERY = 20000                 # số chunk gom lại mỗi lần ghi parquet

META_COLS = ['id', 'document_number', 'title', 'legal_type', 'legal_sectors',
             'issuing_authority', 'issuance_date', 'effect_date', 'effect_status']

OUT_FIELDS = ['chunk_id', 'text', 'doc_id', 'document_number', 'title',
              'legal_type', 'legal_sectors', 'issuing_authority',
              'issuance_date', 'effect_date', 'effect_status']


SEPARATORS = ["\nĐiều ", "\nChương ", "\nMục ", "\n\n", "\n", ". ", " ", ""]


def _split_recursive(text, seps):
    """Tách text bằng separator ưu tiên cao nhất còn tách được; trả về list đoạn nhỏ."""
    if len(text) <= CHUNK_SIZE:
        return [text]
    sep = ""
    rest = seps
    for i, s in enumerate(seps):
        if s == "":
            sep = ""
            rest = seps[i + 1:]
            break
        if s in text:
            sep = s
            rest = seps[i + 1:]
            break
    if sep == "":
        # không còn separator -> cắt cứng theo ký tự
        return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
    parts = text.split(sep)
    pieces = []
    for j, p in enumerate(parts):
        piece = (sep + p) if (j > 0 and sep.strip()) else p  # giữ "Điều"/"Chương" ở đầu đoạn
        if len(piece) > CHUNK_SIZE:
            pieces.extend(_split_recursive(piece, rest))
        elif piece:
            pieces.append(piece)
    return pieces


def split_text(text):
    """Gộp các đoạn nhỏ thành chunk ~CHUNK_SIZE, có overlap CHUNK_OVERLAP."""
    pieces = _split_recursive(text, SEPARATORS)
    chunks, cur = [], ""
    for p in pieces:
        if cur and len(cur) + len(p) > CHUNK_SIZE:
            chunks.append(cur.strip())
            # overlap: lấy đuôi của chunk trước làm đầu chunk sau
            cur = (cur[-CHUNK_OVERLAP:] + p) if CHUNK_OVERLAP else p
        else:
            cur += p
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def clean_text(t):
    """Làm sạch NHẸ: giữ cấu trúc xuống dòng (để chunk theo Điều) và dấu câu/số hiệu."""
    if not isinstance(t, str):
        return ""
    t = t.replace("\r", "")
    t = t.replace(" | ", " ")          # bỏ ký tự ngăn cột header đặc thù dataset
    t = re.sub(r"[ \t]+", " ", t)       # gộp khoảng trắng/tab
    t = re.sub(r" *\n *", "\n", t)       # cắt khoảng trắng quanh xuống dòng
    t = re.sub(r"\n{3,}", "\n\n", t)     # gộp >2 dòng trống
    return t.strip()


def main():
    print("1) Đọc & lọc metadata...")
    meta = pq.read_table(META_PATH, columns=META_COLS).to_pandas()
    mask = meta['legal_sectors'].astype(str).str.contains(SECTOR_PATTERN, case=False, na=False)
    med = meta[mask].copy()
    print(f"   Văn bản ngành y tế: {len(med):,}")
    if KEEP_STATUSES is not None:
        before = len(med)
        med = med[med['effect_status'].isin(KEEP_STATUSES)]
        print(f"   Lọc hiệu lực {KEEP_STATUSES}: giữ {len(med):,}, loại {before-len(med):,}")
    # dict id -> metadata (1 dòng/id)
    meta_map = {r['id']: r for _, r in med.iterrows()}
    medical_ids = set(meta_map.keys())
    print(f"   Tổng id cần lấy nội dung: {len(medical_ids):,}")

    print("2) Stream content, chunk theo Điều/Chương, khử trùng lặp, ghi parquet...")
    cf = pq.ParquetFile(CONTENT_PATH)
    seen_hashes = set()
    buffer = {k: [] for k in OUT_FIELDS}
    writer = None
    n_docs = n_chunks = n_dup = 0

    def flush():
        nonlocal writer
        if not buffer['chunk_id']:
            return
        table = pa.table({k: buffer[k] for k in OUT_FIELDS})
        if writer is None:
            writer = pq.ParquetWriter(OUT_PARQUET, table.schema, compression='zstd')
        writer.write_table(table)
        for k in buffer:
            buffer[k].clear()

    total_batches = cf.metadata.num_rows // 50000 + 1
    for batch in tqdm(cf.iter_batches(batch_size=50000, columns=['id', 'content']),
                      total=total_batches, unit='batch'):
        d = batch.to_pydict()
        for doc_id, content in zip(d['id'], d['content']):
            if doc_id not in medical_ids:
                continue
            text = clean_text(content)
            if len(text) < MIN_CHUNK_LEN:
                continue
            n_docs += 1
            m = meta_map[doc_id]
            for idx, chunk in enumerate(split_text(text)):
                chunk = chunk.strip()
                if len(chunk) < MIN_CHUNK_LEN:
                    continue
                h = hashlib.blake2b(chunk.encode('utf-8'), digest_size=16).digest()
                if h in seen_hashes:
                    n_dup += 1
                    continue
                seen_hashes.add(h)
                buffer['chunk_id'].append(f"{doc_id}_{idx}")
                buffer['text'].append(chunk)
                buffer['doc_id'].append(str(doc_id))
                buffer['document_number'].append(str(m['document_number']))
                buffer['title'].append(str(m['title']))
                buffer['legal_type'].append(str(m['legal_type']))
                buffer['legal_sectors'].append(str(m['legal_sectors']))
                buffer['issuing_authority'].append(str(m['issuing_authority']))
                buffer['issuance_date'].append(str(m['issuance_date']))
                buffer['effect_date'].append(str(m['effect_date']))
                buffer['effect_status'].append(str(m['effect_status']))
                n_chunks += 1
                if len(buffer['chunk_id']) >= FLUSH_EVERY:
                    flush()
    flush()
    if writer is not None:
        writer.close()

    print(f"\n✅ HOÀN TẤT")
    print(f"   Văn bản xử lý : {n_docs:,}")
    print(f"   Chunk ghi ra  : {n_chunks:,}")
    print(f"   Chunk trùng bỏ: {n_dup:,}")
    print(f"   File          : {OUT_PARQUET} ({os.path.getsize(OUT_PARQUET)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
