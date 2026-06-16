# -*- coding: utf-8 -*-
"""Đánh giá lại trên bộ câu tự nhiên MỞ RỘNG (228 câu) — xác nhận tính ổn định.
3 cấu hình: bge-m3 vector / +từ điển / +từ điển+ngữ nghĩa(K3,τ0.45). Strict + topic-level.
Chạy: python train/eval_natural_expanded.py"""
import sys, os, json, pickle, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from sentence_transformers import SentenceTransformer
import chromadb, torch
from query_expand import expand_query

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]
WHERE = {"effect_status": "In effect"}; KS = [1, 3, 5, 10]
DEV = "cuda" if torch.cuda.is_available() else "cpu"
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


def main():
    t0 = time.time()
    bge = SentenceTransformer("BAAI/bge-m3", device=DEV)
    if DEV == "cuda": bge.half()
    bge.max_seq_length = 256
    coll = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db")).get_collection("bge_m3")
    lex = json.load(open(os.path.join(HERE, "lexicon.json"), encoding="utf-8"))
    lex_emb = np.load(os.path.join(HERE, "lexicon_emb.npy")).astype(np.float32)

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

    def sem(qvec, K=3, tau=0.45):
        sims = lex_emb @ np.asarray(qvec, dtype=np.float32)
        return [lex[j] for j in np.argsort(-sims)[:K] if sims[j] >= tau]

    def retrieve(query):
        emb = bge.encode([query], normalize_embeddings=True).tolist()
        r = coll.query(query_embeddings=emb, n_results=15, where=WHERE, include=["metadatas"])
        seen = []
        for m in r["metadatas"][0]:
            dn = m.get("document_number")
            if dn and dn not in seen: seen.append(dn)
        return seen

    cfgs = {"base": {}, "dict": {}, "dict_sem": {}}
    for n, i in enumerate(NAT):
        q = golden[i]["q"]
        qd = expand_query(q)
        qvec = bge.encode([q], normalize_embeddings=True)[0]
        terms = sem(qvec)
        cfgs["base"][i] = retrieve(q)
        cfgs["dict"][i] = retrieve(qd)
        cfgs["dict_sem"][i] = retrieve(qd + (" " + " ".join(terms) if terms else ""))
        if (n + 1) % 40 == 0:
            print(f"  {n+1}/{len(NAT)} ({time.time()-t0:.0f}s)", flush=True)

    res = {}
    for c, da in cfgs.items():
        res[c + "_strict"] = metrics([(da[i], rs(i)) for i in NAT])
        res[c + "_topic"] = metrics([(da[i], rt(i)) for i in NAT])
    json.dump(res, open(os.path.join(HERE, "eval_natural_expanded.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n=== {len(NAT)} câu tự nhiên (bộ mở rộng) ===")
    for c in cfgs:
        print(f"  {c:9} strict", res[c + "_strict"], "| topic", res[c + "_topic"])
    print("✅ Lưu train/eval_natural_expanded.json")


if __name__ == "__main__":
    main()
