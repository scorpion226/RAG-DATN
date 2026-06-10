"""
build_bm25.py — Xây chỉ mục BM25 (từ vựng) song song với vector index.

Vì sao (cho báo cáo): vector search nắm NGỮ NGHĨA nhưng yếu với từ khóa hiếm / số hiệu
văn bản (vd "147/2025/NĐ-CP"). BM25 chấm theo trùng khớp từ vựng -> bù đúng điểm yếu này.
Kết hợp 2 nguồn (hybrid) bằng Reciprocal Rank Fusion thường tốt hơn từng cái riêng.

Chạy: python build_bm25.py   -> tạo thư mục bm25_index/ + bm25_meta.pkl
"""
import sys, pickle
sys.stdout.reconfigure(encoding="utf-8")
import pyarrow.parquet as pq
from tqdm import tqdm
import bm25s

PARQUET = "legal_medical_chunks_clean.parquet"
INDEX_DIR = "bm25_index"
META_PKL = "bm25_meta.pkl"
META_KEYS = ['chunk_id', 'document_number', 'title', 'legal_type',
             'issuing_authority', 'issuance_date', 'effect_date', 'effect_status', 'doc_id']


def main():
    pf = pq.ParquetFile(PARQUET)
    total = pf.metadata.num_rows
    texts, meta = [], []
    print(f"Đọc {total:,} chunk...")
    for b in tqdm(pf.iter_batches(batch_size=20000), total=total // 20000 + 1):
        rows = b.to_pylist()
        for r in rows:
            texts.append(r['text'])
            meta.append({k: r[k] for k in META_KEYS})

    print("Tokenize + xây BM25 (lowercase, không stopword)...")
    corpus_tokens = bm25s.tokenize(texts, stopwords=None, show_progress=True)
    retriever = bm25s.BM25()
    retriever.index(corpus_tokens, show_progress=True)
    retriever.save(INDEX_DIR)              # lưu chỉ mục (không lưu corpus để gọn)
    with open(META_PKL, "wb") as f:
        pickle.dump(meta, f)
    print(f"\n✅ Đã lưu BM25 index ({len(texts):,} chunk) vào {INDEX_DIR}/ + {META_PKL}")


if __name__ == "__main__":
    main()
