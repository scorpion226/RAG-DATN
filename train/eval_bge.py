# -*- coding: utf-8 -*-
"""So sánh mô hình embedding bge-m3 (collection bge_m3, text thô) vs PhoBERT
(collection legal_medical, tách từ) — TRUY XUẤT MỞ THẬT trên toàn corpus.
Đo trên 100 câu tự nhiên (nhãn nghiêm ngặt + topic-level) và 200 câu mẫu (canh không tụt).
Chạy: python train/eval_bge.py"""
import sys, os, json, pickle
sys.stdout.reconfigure(encoding="utf-8")
from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer
import chromadb, torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
WHERE = {"effect_status": "In effect"}
KS = [1, 3, 5, 10]
DEV = "cuda" if torch.cuda.is_available() else "cpu"
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]
SAMPLE = [i for i, q in enumerate(golden) if q.get("type") in (None, "generated")][:200]

# ---- topic-level family ----
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


def dedup(metas):
    seen = []
    for m in metas:
        dn = m.get("document_number")
        if dn and dn not in seen: seen.append(dn)
    return seen


def run(model, coll, ids, seg):
    out = []
    for i in ids:
        q = golden[i]["q"]
        text = ViTokenizer.tokenize(q) if seg else q
        emb = model.encode([text], normalize_embeddings=True).tolist()
        r = coll.query(query_embeddings=emb, n_results=20, where=WHERE, include=["metadatas"])
        out.append((dedup(r["metadatas"][0]), i))
    return out


def main():
    client = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db"))
    meta = pickle.load(open(os.path.join(ROOT, "bm25_meta.pkl"), "rb"))
    dn2t = {}
    for m in meta:
        dn = m.get("document_number")
        if dn and dn not in dn2t: dn2t[dn] = (m.get("title", "") or "").lower()
    fam = {law: {dn for dn, t in dn2t.items() if nm in t and any(mk in t for mk in MARK)}
           for law, nm in LAWNAME.items()}

    def rel_strict(i): return set(golden[i]["relevant"])
    def rel_topic(i):
        s = set(golden[i]["relevant"])
        for law in list(s): s |= fam.get(law, set())
        return s

    res = {}
    # PhoBERT (legal_medical, segment)
    pho = SentenceTransformer("bkai-foundation-models/vietnamese-bi-encoder", device=DEV)
    cph = client.get_collection("legal_medical")
    nat_pho = run(pho, cph, NAT, seg=True)
    smp_pho = run(pho, cph, SAMPLE, seg=True)
    res["PhoBERT_nat_strict"] = metrics([(d, rel_strict(i)) for d, i in nat_pho])
    res["PhoBERT_nat_topic"] = metrics([(d, rel_topic(i)) for d, i in nat_pho])
    res["PhoBERT_sample_strict"] = metrics([(d, rel_strict(i)) for d, i in smp_pho])
    # bge-m3 (bge_m3, raw)
    bge = SentenceTransformer("BAAI/bge-m3", device=DEV)
    if DEV == "cuda": bge.half()
    bge.max_seq_length = 256
    cbge = client.get_collection("bge_m3")
    print("bge_m3 count:", cbge.count())
    nat_bge = run(bge, cbge, NAT, seg=False)
    smp_bge = run(bge, cbge, SAMPLE, seg=False)
    res["bge_nat_strict"] = metrics([(d, rel_strict(i)) for d, i in nat_bge])
    res["bge_nat_topic"] = metrics([(d, rel_topic(i)) for d, i in nat_bge])
    res["bge_sample_strict"] = metrics([(d, rel_strict(i)) for d, i in smp_bge])

    json.dump(res, open(os.path.join(os.path.dirname(__file__), "eval_bge.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n=== SO SÁNH (truy xuất vector MỞ, toàn corpus) ===")
    for k, v in res.items():
        print(f"  {k:24}", v)
    print("✅ Lưu train/eval_bge.json")


if __name__ == "__main__":
    main()
