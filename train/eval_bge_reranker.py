# -*- coding: utf-8 -*-
"""Thử reranker CÙNG HỌ bge: bge-reranker-v2-m3 (thay PhoRanker vốn làm hại bge-m3).
Trên 100 câu TN: bge-m3 vector+dict (top-30) -> bge-reranker-v2-m3 -> top-10.
Chạy: python train/eval_bge_reranker.py"""
import sys, os, json, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
from sentence_transformers import SentenceTransformer, CrossEncoder
import chromadb, torch
from query_expand import expand_query

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
WHERE = {"effect_status": "In effect"}; KS = [1, 3, 5, 10]
DEV = "cuda" if torch.cuda.is_available() else "cpu"
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]
LAWNAME = {"15/2023/QH15": "luật khám bệnh, chữa bệnh", "105/2016/QH13": "luật dược",
           "44/2024/QH15": "luật dược", "39/VBHN-VPQH": "luật dược",
           "55/2010/QH12": "luật an toàn thực phẩm", "61/VBHN-VPQH": "luật an toàn thực phẩm",
           "02/VBHN-VPQH": "luật an toàn thực phẩm", "46/2014/QH13": "luật bảo hiểm y tế",
           "51/2024/QH15": "luật bảo hiểm y tế", "09/2012/QH13": "phòng, chống tác hại của thuốc lá",
           "08/VBHN-VPQH": "phòng, chống tác hại của thuốc lá", "15/VBHN-VPQH": "phòng, chống tác hại của thuốc lá",
           "11/VBHN-VPQH": "phòng, chống tác hại của thuốc lá", "44/2019/QH14": "phòng, chống tác hại của rượu, bia",
           "75/2006/QH11": "hiến, lấy, ghép mô", "64/2006/QH11": "phòng, chống nhiễm vi rút gây ra hội chứng",
           "33/VBHN-VPQH": "phòng, chống nhiễm vi rút gây ra hội chứng", "114/2025/QH15": "luật phòng bệnh"}
MARK = ["hướng dẫn", "hợp nhất", "quy định chi tiết", "biện pháp thi hành", "quy định và biện pháp"]


def metrics(items):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(items)
    for docs, rel in items:
        first = next((i + 1 for i, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]): hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3), "n": n}


def dd(metas):
    seen = []
    for m in metas:
        dn = m.get("document_number")
        if dn and dn not in seen: seen.append(dn)
    return seen


def main():
    meta = pickle.load(open(os.path.join(ROOT, "bm25_meta.pkl"), "rb"))
    dn2t = {}
    for m in meta:
        dn = m.get("document_number")
        if dn and dn not in dn2t: dn2t[dn] = (m.get("title", "") or "").lower()
    fam = {law: {dn for dn, t in dn2t.items() if nm in t and any(mk in t for mk in MARK)} for law, nm in LAWNAME.items()}
    def rs(i): return set(golden[i]["relevant"])
    def rt(i):
        s = set(golden[i]["relevant"])
        for law in list(s): s |= fam.get(law, set())
        return s

    print("Nạp bge-m3 + bge-reranker-v2-m3 (GPU)...", flush=True)
    bge = SentenceTransformer("BAAI/bge-m3", device=DEV)
    if DEV == "cuda": bge.half()
    bge.max_seq_length = 256
    ce = CrossEncoder("BAAI/bge-reranker-v2-m3", max_length=512, device=DEV)
    coll = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db")).get_collection("bge_m3")

    base, reranked = [], []
    for i in NAT:
        q = golden[i]["q"]; qd = expand_query(q)
        emb = bge.encode([qd], normalize_embeddings=True).tolist()
        res = coll.query(query_embeddings=emb, n_results=30, where=WHERE, include=["documents", "metadatas"])
        metas, docs = res["metadatas"][0], res["documents"][0]
        base.append((dd(metas[:10]), i))
        scores = ce.predict([[q, d] for d in docs])
        order = sorted(range(len(docs)), key=lambda j: scores[j], reverse=True)
        reranked.append((dd([metas[j] for j in order])[:10], i))

    res = {"vector_dict_strict": metrics([(d, rs(i)) for d, i in base]),
           "vector_dict_topic": metrics([(d, rt(i)) for d, i in base]),
           "vector_dict_bgererank_strict": metrics([(d, rs(i)) for d, i in reranked]),
           "vector_dict_bgererank_topic": metrics([(d, rt(i)) for d, i in reranked])}
    json.dump(res, open(os.path.join(os.path.dirname(__file__), "eval_bge_reranker.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n=== bge-m3 vector+dict, reranker bge-reranker-v2-m3 (100 câu TN) ===")
    for k, v in res.items(): print(f"  {k:32}", v)
    print("✅ Lưu train/eval_bge_reranker.json")


if __name__ == "__main__":
    main()
