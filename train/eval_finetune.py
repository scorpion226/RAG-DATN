# -*- coding: utf-8 -*-
"""Đánh giá CLOSED-POOL model fine-tune vs gốc trên 29 câu TEST (giữ riêng, không huấn luyện).

PHƯƠNG PHÁP (ghi rõ là hạn chế trong báo cáo):
  Fine-tune bộ mã hóa làm 367k vector chunk cũ không tương thích (embed lại = 13h/lần).
  Thay vào đó đánh giá CLOSED-POOL: mỗi câu test dựng một pool ứng viên =
    top-150 chunk base-vector (distractor thực tế) ∪ top-10 chunk của mỗi luật đúng
  (bơm chunk luật đúng để model có cơ hội xếp lại công bằng — nên CON SỐ TUYỆT ĐỐI là
   "độ xếp hạng lại khi đáp án có trong pool", KHÔNG so trực tiếp với Hit@k truy xuất mở).
  Với mỗi (model, biến thể truy vấn) embed lại pool + query rồi xếp theo cosine,
  dedup theo số hiệu -> Hit@k/MRR ở mức luật. So 4 điều kiện: base, base+dict, ft, ft+dict.
Lưu train/eval_finetune.json. Chạy: python train/eval_finetune.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
split = json.load(open(os.path.join(HERE, "ft_split.json"), encoding="utf-8"))
TEST = split["test"]

from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer
import numpy as np
import chromadb
from query_expand import expand_query

EMBED_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"
FT_MODEL = os.path.join(ROOT, "models", "ft-bi-encoder")
CHROMA_DIR = os.path.join(ROOT, "chroma_db"); COLLECTION = "legal_medical"
WHERE = {"effect_status": "In effect"}
KS = [1, 3, 5, 10]


def seg(t):
    return ViTokenizer.tokenize(t)


def build_pool(coll, base_model, q, rels):
    """Pool = top-150 base-vector ∪ top-10 mỗi luật đúng. Trả về (texts, docnums)."""
    emb = base_model.encode([seg(q)], normalize_embeddings=True).tolist()
    r = coll.query(query_embeddings=emb, n_results=150, where=WHERE,
                   include=["documents", "metadatas"])
    texts, dns = [], []
    seen_ids = set()
    for d, m in zip(r["documents"][0], r["metadatas"][0]):
        texts.append(d); dns.append(m.get("document_number"))
    # bơm chunk luật đúng
    try:
        g = coll.get(where={"document_number": {"$in": rels}}, limit=10 * len(rels),
                     include=["documents", "metadatas"])
        for d, m in zip(g["documents"], g["metadatas"]):
            texts.append(d); dns.append(m.get("document_number"))
    except Exception:
        pass
    return texts, dns


def rank_with(pool_emb, pool_dns, query_emb):
    """Xếp hạng pool đã embed sẵn theo cosine tới query đã embed sẵn (chuẩn hóa rồi)."""
    sims = pool_emb @ query_emb
    out = []
    for idx in np.argsort(-sims):
        dn = pool_dns[idx]
        if dn and dn not in out:
            out.append(dn)
    return out


def metrics(items):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(items)
    for docs, rel in items:
        first = next((i + 1 for i, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]):
                hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3), "n": n}


def main():
    print(f"Test: {len(TEST)} câu. Nạp base + ft model + Chroma...", flush=True)
    base = SentenceTransformer(EMBED_MODEL, device="cpu")
    ft = SentenceTransformer(FT_MODEL, device="cpu")
    coll = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION)

    rows = {c: [] for c in ["base", "base_dict", "ft", "ft_dict"]}
    for n, i in enumerate(TEST):
        q = golden[i]["q"]; rel = set(golden[i]["relevant"])
        qx = expand_query(q)
        texts, dns = build_pool(coll, base, q, list(rel))
        seg_pool = [seg(t) for t in texts]               # tách từ pool 1 LẦN
        base_pe = base.encode(seg_pool, normalize_embeddings=True, batch_size=64)
        ft_pe = ft.encode(seg_pool, normalize_embeddings=True, batch_size=64)
        sq, sqx = seg(q), seg(qx)
        b_q = base.encode([sq], normalize_embeddings=True)[0]
        b_qx = base.encode([sqx], normalize_embeddings=True)[0]
        f_q = ft.encode([sq], normalize_embeddings=True)[0]
        f_qx = ft.encode([sqx], normalize_embeddings=True)[0]
        rows["base"].append((rank_with(base_pe, dns, b_q), rel))
        rows["base_dict"].append((rank_with(base_pe, dns, b_qx), rel))
        rows["ft"].append((rank_with(ft_pe, dns, f_q), rel))
        rows["ft_dict"].append((rank_with(ft_pe, dns, f_qx), rel))
        print(f"  {n+1}/{len(TEST)}", flush=True)

    res = {c: metrics(v) for c, v in rows.items()}
    json.dump({"n_test": len(TEST), "results": res, "test_ids": TEST,
               "note": "closed-pool: top150 base-vector + bơm chunk luật đúng; số tuyệt đối là độ xếp hạng lại"},
              open(os.path.join(HERE, "eval_finetune.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n=== KẾT QUẢ closed-pool (29 câu test) ===")
    for c in ["base", "base_dict", "ft", "ft_dict"]:
        print(f"  {c:10}", res[c])
    print("✅ Lưu eval_finetune.json")


if __name__ == "__main__":
    main()
