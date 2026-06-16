# -*- coding: utf-8 -*-
"""Đánh giá LARGE-POOL model fine-tune lớn vs gốc trên TOÀN BỘ 100 câu tự nhiên.

100 câu tự nhiên KHÔNG nằm trong dữ liệu huấn luyện (đã loại các luật eval) -> sạch.
Pool dùng CHUNG cho cả 100 câu = hợp (top-200 base-vector mỗi câu) ∪ (toàn bộ chunk các
luật liên quan + họ văn bản). Embed lại pool MỘT LẦN bằng base và ft -> xếp hạng cosine.
Đo Hit@k/MRR ở mức luật, cả nhãn NGHIÊM NGẶT và TOPIC-LEVEL (họ văn bản).
So 4 điều kiện: base, base+dict, ft, ft+dict. Lưu train/eval_large_pool.json.
Chạy: python train/eval_large_pool.py [tên_thư_mục_model_ft]   (mặc định ft-bi-encoder-large)
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
import pickle
from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer
import numpy as np
import chromadb
from query_expand import expand_query

EMBED_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"
FT_DIR = sys.argv[1] if len(sys.argv) > 1 else "ft-bi-encoder-large"
FT_MODEL = os.path.join(ROOT, "models", FT_DIR)
CHROMA_DIR = os.path.join(ROOT, "chroma_db"); COLLECTION = "legal_medical"
WHERE = {"effect_status": "In effect"}
KS = [1, 3, 5, 10]
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]

# ---- nhãn topic-level (họ văn bản: hướng dẫn/hợp nhất nhắc đích danh tên luật) ----
LAWNAME = {
    "15/2023/QH15": "luật khám bệnh, chữa bệnh",
    "105/2016/QH13": "luật dược", "44/2024/QH15": "luật dược", "39/VBHN-VPQH": "luật dược",
    "55/2010/QH12": "luật an toàn thực phẩm", "61/VBHN-VPQH": "luật an toàn thực phẩm",
    "02/VBHN-VPQH": "luật an toàn thực phẩm",
    "46/2014/QH13": "luật bảo hiểm y tế", "51/2024/QH15": "luật bảo hiểm y tế",
    "09/2012/QH13": "phòng, chống tác hại của thuốc lá", "08/VBHN-VPQH": "phòng, chống tác hại của thuốc lá",
    "15/VBHN-VPQH": "phòng, chống tác hại của thuốc lá", "11/VBHN-VPQH": "phòng, chống tác hại của thuốc lá",
    "44/2019/QH14": "phòng, chống tác hại của rượu, bia",
    "75/2006/QH11": "hiến, lấy, ghép mô",
    "64/2006/QH11": "phòng, chống nhiễm vi rút gây ra hội chứng",
    "33/VBHN-VPQH": "phòng, chống nhiễm vi rút gây ra hội chứng",
    "114/2025/QH15": "luật phòng bệnh",
}
MARK = ["hướng dẫn", "hợp nhất", "quy định chi tiết", "biện pháp thi hành", "quy định và biện pháp"]


def seg(t):
    return ViTokenizer.tokenize(t)


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
    print(f"Model ft: {FT_MODEL}\nNạp base + ft + Chroma...", flush=True)
    base = SentenceTransformer(EMBED_MODEL, device="cpu")
    ft = SentenceTransformer(FT_MODEL, device="cpu")
    coll = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION)

    # họ văn bản topic-level
    meta = pickle.load(open(os.path.join(ROOT, "bm25_meta.pkl"), "rb"))
    dn2title = {}
    for m in meta:
        dn = m.get("document_number")
        if dn and dn not in dn2title:
            dn2title[dn] = (m.get("title", "") or "").lower()
    famcache = {}
    for law, nm in LAWNAME.items():
        famcache[law] = {dn for dn, t in dn2title.items() if nm in t and any(mk in t for mk in MARK)}

    # ---- dựng pool CHUNG ----
    print("Dựng pool chung (top-200 mỗi câu + chunk các luật liên quan)...", flush=True)
    pool_ids, pool_text, pool_dn = [], [], []
    seen_ids = set()
    rels_all = set()
    for i in NAT:
        rels_all.update(golden[i]["relevant"])
        emb = base.encode([seg(golden[i]["q"])], normalize_embeddings=True).tolist()
        r = coll.query(query_embeddings=emb, n_results=200, where=WHERE,
                       include=["documents", "metadatas"])
        for cid, doc, m in zip(r["ids"][0], r["documents"][0], r["metadatas"][0]):
            if cid not in seen_ids:
                seen_ids.add(cid); pool_ids.append(cid); pool_text.append(doc)
                pool_dn.append(m.get("document_number"))
    # toàn bộ chunk các luật liên quan (để truy xuất "mở" trong subcorpus)
    for law in sorted(rels_all):
        try:
            g = coll.get(where={"document_number": law}, include=["documents", "metadatas"])
            for cid, doc, m in zip(g["ids"], g["documents"], g["metadatas"]):
                if cid not in seen_ids:
                    seen_ids.add(cid); pool_ids.append(cid); pool_text.append(doc)
                    pool_dn.append(m.get("document_number"))
        except Exception:
            pass
    print(f"Pool: {len(pool_ids):,} chunk. Embed lại bằng base & ft...", flush=True)
    seg_pool = [seg(t) for t in pool_text]
    base_pe = base.encode(seg_pool, normalize_embeddings=True, batch_size=64, show_progress_bar=True)
    ft_pe = ft.encode(seg_pool, normalize_embeddings=True, batch_size=64, show_progress_bar=True)
    pool_dn = np.array(pool_dn, dtype=object)

    def rank(pe, qvec):
        out = []
        for idx in np.argsort(-(pe @ qvec)):
            dn = pool_dn[idx]
            if dn and dn not in out:
                out.append(dn)
            if len(out) >= 15:
                break
        return out

    conds = {"base": [], "base_dict": [], "ft": [], "ft_dict": []}
    for i in NAT:
        q = golden[i]["q"]; qx = expand_query(q)
        bq = base.encode([seg(q)], normalize_embeddings=True)[0]
        bqx = base.encode([seg(qx)], normalize_embeddings=True)[0]
        fq = ft.encode([seg(q)], normalize_embeddings=True)[0]
        fqx = ft.encode([seg(qx)], normalize_embeddings=True)[0]
        conds["base"].append((rank(base_pe, bq), i))
        conds["base_dict"].append((rank(base_pe, bqx), i))
        conds["ft"].append((rank(ft_pe, fq), i))
        conds["ft_dict"].append((rank(ft_pe, fqx), i))

    def rel_strict(i):
        return set(golden[i]["relevant"])

    def rel_topic(i):
        s = set(golden[i]["relevant"])
        for law in list(s):
            s |= famcache.get(law, set())
        return s

    out = {"n": len(NAT), "pool": len(pool_ids), "ft_model": FT_DIR, "strict": {}, "topic": {}}
    for c, lst in conds.items():
        out["strict"][c] = metrics([(docs, rel_strict(i)) for docs, i in lst])
        out["topic"][c] = metrics([(docs, rel_topic(i)) for docs, i in lst])
    json.dump(out, open(os.path.join(HERE, "eval_large_pool.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n=== STRICT (100 câu tự nhiên) ===")
    for c in conds:
        print(f"  {c:10}", out["strict"][c])
    print("=== TOPIC-LEVEL ===")
    for c in conds:
        print(f"  {c:10}", out["topic"][c])
    print("✅ Lưu eval_large_pool.json")


if __name__ == "__main__":
    main()
