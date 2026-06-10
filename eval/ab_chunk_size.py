"""
ab_chunk_size.py — Thí nghiệm A/B: ảnh hưởng của KÍCH THƯỚC CHUNK tới retrieval.

So sánh 3 cấu hình chunk trên CÙNG một tập tài liệu (các luật trong ground-truth +
tài liệu nhiễu ngẫu nhiên), embed vào 3 collection riêng, đánh giá cùng bộ câu hỏi vàng:
  - fixed-500   : cắt ~500 ký tự, overlap 50
  - fixed-1200  : cắt ~1200 ký tự, overlap 150
  - by-dieu     : cắt theo "Điều"/"Chương" (~1200) — cấu hình của hệ thống

Chạy: python eval/ab_chunk_size.py
"""
import sys, os, re, json, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import pyarrow.parquet as pq
from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer
import chromadb
from build_chunks import clean_text, split_text as split_by_dieu

SNAP = (r"C:\Users\admin/.cache/huggingface/hub/datasets--th1nhng0--vietnamese-legal-documents/"
        r"snapshots/0a39ad7eae8e6c188cb225c4b1443c3b346461d8/legacy")
EMBED_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"
AB_DIR = "chroma_ab"
N_DISTRACTOR = 200
KS = [1, 3, 5, 10]
MIN_LEN = 80


def fixed_chunks(text, size, overlap):
    out, start = [], 0
    while start < len(text):
        end = start + size
        if end >= len(text):
            c = text[start:].strip()
            if len(c) >= MIN_LEN: out.append(c)
            break
        sp = text.rfind(" ", start, end)
        if sp == -1 or sp <= start: sp = end
        c = text[start:sp].strip()
        if len(c) >= MIN_LEN: out.append(c)
        start = max(sp - overlap, start + 1)
    return out


CONFIGS = {
    "fixed-500":  lambda t: fixed_chunks(t, 500, 50),
    "fixed-1200": lambda t: fixed_chunks(t, 1200, 150),
    "by-dieu":    split_by_dieu,
}


def main():
    golden = json.load(open(os.path.join(os.path.dirname(__file__), "golden_questions.json"), encoding="utf-8"))
    relevant_dns = set(dn for it in golden for dn in it["relevant"])

    # 1) Chọn tập tài liệu mẫu: docs liên quan (theo số hiệu) + nhiễu
    meta = pq.read_table(SNAP + r"/metadata.parquet",
                         columns=['id', 'document_number', 'legal_sectors', 'effect_status']).to_pandas()
    med = meta[meta['legal_sectors'].astype(str).str.contains("Health|Y tế", case=False, na=False)]
    med = med[med['effect_status'] == "In effect"]
    rel_ids = med[med['document_number'].isin(relevant_dns)]['id'].tolist()
    pool = [i for i in med['id'].tolist() if i not in set(rel_ids)]
    random.seed(42)
    sample_ids = set(rel_ids) | set(random.sample(pool, min(N_DISTRACTOR, len(pool))))
    dn_of = dict(zip(med['id'], med['document_number']))
    print(f"Tài liệu liên quan: {len(rel_ids)} | tổng mẫu (kèm nhiễu): {len(sample_ids)}")

    # 2) Lấy nội dung gốc cho tập mẫu
    docs = {}
    cf = pq.ParquetFile(SNAP + r"/content.parquet")
    for b in cf.iter_batches(batch_size=50000, columns=['id', 'content']):
        d = b.to_pydict()
        for i, c in zip(d['id'], d['content']):
            if i in sample_ids:
                docs[i] = clean_text(c)
    print(f"Đã lấy nội dung {len(docs)} tài liệu")

    model = SentenceTransformer(EMBED_MODEL, device="cpu")
    client = chromadb.PersistentClient(path=AB_DIR)

    results = {}
    for cfg, splitter in CONFIGS.items():
        cname = "cfg_" + cfg.replace("-", "_")
        try: client.delete_collection(cname)
        except Exception: pass
        coll = client.create_collection(cname, metadata={"hnsw:space": "cosine"})
        ids, texts, metas = [], [], []
        for did, text in docs.items():
            if len(text) < MIN_LEN: continue
            for j, ch in enumerate(splitter(text)):
                ch = ch.strip()
                if len(ch) < MIN_LEN: continue
                ids.append(f"{did}_{j}"); texts.append(ch)
                metas.append({"document_number": str(dn_of.get(did, ""))})
        print(f"[{cfg}] {len(texts):,} chunk — đang embed...")
        # embed + add theo batch
        B = 256
        for s in range(0, len(texts), B):
            seg = [ViTokenizer.tokenize(t) for t in texts[s:s+B]]
            emb = model.encode(seg, normalize_embeddings=True, show_progress_bar=False).tolist()
            coll.add(ids=ids[s:s+B], embeddings=emb, metadatas=metas[s:s+B])
        # đánh giá
        hits_at = {k: 0 for k in KS}; rr = 0.0
        for it in golden:
            seg = ViTokenizer.tokenize(it["q"])
            qe = model.encode([seg], normalize_embeddings=True).tolist()
            r = coll.query(query_embeddings=qe, n_results=10, include=["metadatas"])
            ranked = [m["document_number"] for m in r["metadatas"][0]]
            rel = set(it["relevant"])
            first = next((i+1 for i, dn in enumerate(ranked) if dn in rel), None)
            rr += (1.0/first) if first else 0.0
            for k in KS:
                if any(dn in rel for dn in ranked[:k]): hits_at[k] += 1
        n = len(golden)
        results[cfg] = {"chunks": len(texts), **{f"Hit@{k}": round(hits_at[k]/n, 3) for k in KS},
                        "MRR": round(rr/n, 3)}
        print(f"[{cfg}] {results[cfg]}")

    print("\n=== BẢNG KẾT QUẢ (chunk-size) ===")
    print(f"{'cấu hình':12} {'#chunk':>8} {'Hit@1':>6} {'Hit@3':>6} {'Hit@5':>6} {'Hit@10':>7} {'MRR':>6}")
    for cfg, r in results.items():
        print(f"{cfg:12} {r['chunks']:>8,} {r['Hit@1']:>6} {r['Hit@3']:>6} {r['Hit@5']:>6} {r['Hit@10']:>7} {r['MRR']:>6}")


if __name__ == "__main__":
    main()
