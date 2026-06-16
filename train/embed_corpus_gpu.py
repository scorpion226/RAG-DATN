# -*- coding: utf-8 -*-
"""Embed toàn corpus bằng GPU với MỘT model tùy chọn -> collection ChromaDB riêng.
Dùng để thử mô hình embedding mạnh hơn (bge-m3, e5...) hoặc model fine-tune.
RESUME được (theo collection.count()). GPU giúp 367k chunk còn ~30-60 phút thay vì 13h.

Chạy: python train/embed_corpus_gpu.py <model_name> <collection> [segment:0/1] [limit]
  ví dụ: python train/embed_corpus_gpu.py BAAI/bge-m3 bge_m3 0
         python train/embed_corpus_gpu.py bkai-foundation-models/vietnamese-bi-encoder pho 1
segment=1: tách từ pyvi (cho PhoBERT); segment=0: dùng text thô (cho bge-m3/e5).
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
import pyarrow.parquet as pq
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
import chromadb
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARQUET = os.path.join(ROOT, "legal_medical_chunks_clean.parquet")
CHROMA_DIR = os.path.join(ROOT, "chroma_db")     # cùng thư mục, khác collection
META_KEYS = ['document_number', 'title', 'legal_type', 'issuing_authority',
             'issuance_date', 'effect_date', 'effect_status', 'doc_id']

MODEL = sys.argv[1] if len(sys.argv) > 1 else "BAAI/bge-m3"
COLL = sys.argv[2] if len(sys.argv) > 2 else "bge_m3"
SEGMENT = (len(sys.argv) > 3 and sys.argv[3] == "1")
LIMIT = int(sys.argv[4]) if len(sys.argv) > 4 else None
ENCODE_BATCH = 96 if "bge-m3" in MODEL or "large" in MODEL else 256
ADD_BATCH = 2000

if SEGMENT:
    from pyvi import ViTokenizer


def prep(t):
    return ViTokenizer.tokenize(t) if SEGMENT else t


def main():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Model={MODEL} | collection={COLL} | segment={SEGMENT} | device={dev}", flush=True)
    total_all = pq.ParquetFile(PARQUET).metadata.num_rows
    total = min(LIMIT, total_all) if LIMIT else total_all
    model = SentenceTransformer(MODEL, device=dev, trust_remote_code=True)
    model.max_seq_length = min(getattr(model, "max_seq_length", 512) or 512, 256)
    if dev == "cuda":
        model.half()   # fp16: nhanh ~2x + giảm VRAM cho model lớn (bge-m3)
    print(f"max_seq_length={model.max_seq_length}, fp16={dev=='cuda'}", flush=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    coll = client.get_or_create_collection(name=COLL, metadata={"hnsw:space": "cosine"})
    already = coll.count()
    print(f"Đã nạp trước: {already:,}/{total:,} -> nạp tiếp.", flush=True)

    pf = pq.ParquetFile(PARQUET); seen = 0
    bi, bd, bm = [], [], []
    pbar = tqdm(total=total, initial=already, unit="chunk")

    def flush():
        if not bi:
            return
        emb = model.encode([prep(d) for d in bd], batch_size=ENCODE_BATCH,
                           normalize_embeddings=True, show_progress_bar=False).tolist()
        coll.add(ids=bi, documents=bd, embeddings=emb, metadatas=bm)
        pbar.update(len(bi)); bi.clear(); bd.clear(); bm.clear()

    for batch in pf.iter_batches(batch_size=5000):
        for r in batch.to_pylist():
            seen += 1
            if seen <= already:
                continue
            if LIMIT and seen > LIMIT:
                flush(); pbar.close(); print(f"\n✅ Xong (limit). {coll.count():,} vector."); return
            bi.append(r['chunk_id']); bd.append(r['text'])
            bm.append({k: r[k] for k in META_KEYS})
            if len(bi) >= ADD_BATCH:
                flush()
    flush(); pbar.close()
    print(f"\n✅ Hoàn tất. Collection '{COLL}' có {coll.count():,} vector.", flush=True)


if __name__ == "__main__":
    main()
