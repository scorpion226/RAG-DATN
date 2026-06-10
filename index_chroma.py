"""
index_chroma.py — GĐ2: tạo embedding (PhoBERT bi-encoder) + nạp vào ChromaDB.

Lý do các bước (cho báo cáo):
  - Embedding bi-encoder dựa trên PhoBERT: ánh xạ văn bản tiếng Việt sang vector
    ngữ nghĩa 768 chiều -> cho phép tìm kiếm theo NGHĨA thay vì từ khóa.
  - Tách từ bằng pyvi (ViTokenizer): PhoBERT huấn luyện trên text đã tách từ
    -> KHÔNG tách thì embedding lệch, recall giảm (có thể thí nghiệm A/B chứng minh).
  - Chuẩn hoá vector (normalize) + cosine: độ đo phù hợp cho similarity search.
  - ChromaDB Persistent: lưu vector + metadata ra đĩa, truy vấn top-k nhanh (HNSW).

Resume được: chạy lại sẽ bỏ qua số chunk đã nạp (theo collection.count()).
Chạy: python index_chroma.py
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import pyarrow.parquet as pq
from tqdm import tqdm
from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer
import chromadb

PARQUET = "legal_medical_chunks_clean.parquet"
CHROMA_DIR = "chroma_db"
COLLECTION = "legal_medical"
EMBED_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"
ENCODE_BATCH = 128          # số chunk encode mỗi lần (giảm nếu thiếu RAM)
ADD_BATCH = 2000            # số bản ghi add vào Chroma mỗi lần (< giới hạn ~5461)

META_KEYS = ['document_number', 'title', 'legal_type', 'issuing_authority',
             'issuance_date', 'effect_date', 'effect_status', 'doc_id']


def segment(text):
    """Tách từ tiếng Việt cho PhoBERT (vd 'Bộ Y tế' -> 'Bộ_Y_tế')."""
    return ViTokenizer.tokenize(text)


def main():
    # Tham so dong lenh: python index_chroma.py [limit]
    #   limit > 0  -> chi nap toi 'limit' chunk dau (index nho de test)
    #   khong co   -> nap toan bo (chay qua dem; resume noi tiep index nho)
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    total_all = pq.ParquetFile(PARQUET).metadata.num_rows
    total = min(limit, total_all) if limit else total_all
    print(f"Tong chunk can nap: {total:,}" + (f" (gioi han {limit:,}/{total_all:,})" if limit else ""))

    print(f"Tai embedding model: {EMBED_MODEL} (lan dau se tai ~500MB)...")
    model = SentenceTransformer(EMBED_MODEL, device="cpu")

    client = chromadb.PersistentClient(path=CHROMA_DIR)
    coll = client.get_or_create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine"})
    already = coll.count()
    print(f"Da nap truoc do: {already:,} -> bo qua, nap tiep tu day.")

    pf = pq.ParquetFile(PARQUET)
    seen = 0
    buf_ids, buf_docs, buf_meta = [], [], []
    pbar = tqdm(total=total, initial=already, unit="chunk")

    def flush_chroma():
        if not buf_ids:
            return
        # encode (trên text ĐÃ tách từ) rồi add kèm embedding + metadata
        seg = [segment(d) for d in buf_docs]
        emb = model.encode(seg, batch_size=ENCODE_BATCH, normalize_embeddings=True,
                           show_progress_bar=False).tolist()
        coll.add(ids=buf_ids, documents=buf_docs, embeddings=emb, metadatas=buf_meta)
        pbar.update(len(buf_ids))
        buf_ids.clear(); buf_docs.clear(); buf_meta.clear()

    for batch in pf.iter_batches(batch_size=5000):
        rows = batch.to_pylist()
        for r in rows:
            seen += 1
            if seen <= already:          # resume: bỏ qua phần đã nạp
                continue
            if limit and seen > limit:   # dừng ở giới hạn (index nhỏ)
                flush_chroma(); pbar.close()
                print(f"\n✅ Index nhỏ xong. Collection '{COLLECTION}' có {coll.count():,} vector.")
                return
            buf_ids.append(r['chunk_id'])
            buf_docs.append(r['text'])
            buf_meta.append({k: r[k] for k in META_KEYS})
            if len(buf_ids) >= ADD_BATCH:
                flush_chroma()
    flush_chroma()
    pbar.close()
    print(f"\n✅ Hoan tat. Collection '{COLLECTION}' co {coll.count():,} vector tai {CHROMA_DIR}/")


if __name__ == "__main__":
    main()
