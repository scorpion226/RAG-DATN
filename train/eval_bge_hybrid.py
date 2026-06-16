# -*- coding: utf-8 -*-
"""Cấu hình ĐẦY ĐỦ bge-m3 + Hybrid (BM25+vector, RRF, nhận diện số hiệu) + Reranker.
So với PhoBERT + Hybrid + Reranker (đã biết: câu mẫu 0.650 / câu TN 0.160).
Đo trên 100 câu tự nhiên (nghiêm ngặt + topic-level) và 200 câu mẫu. Có biến thể + từ điển.
Chạy: python train/eval_bge_hybrid.py"""
import sys, os, json, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
from hybrid import HybridRetriever

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
WHERE = {"effect_status": "In effect"}
KS = [1, 3, 5, 10]
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]
SAMPLE = [i for i, q in enumerate(golden) if q.get("type") in (None, "generated")][:200]

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


def dedup(hits):
    seen = []
    for h in hits:
        dn = h["metadata"].get("document_number")
        if dn and dn not in seen: seen.append(dn)
    return seen


def main():
    meta = pickle.load(open(os.path.join(ROOT, "bm25_meta.pkl"), "rb"))
    dn2t = {}
    for m in meta:
        dn = m.get("document_number")
        if dn and dn not in dn2t: dn2t[dn] = (m.get("title", "") or "").lower()
    fam = {law: {dn for dn, t in dn2t.items() if nm in t and any(mk in t for mk in MARK)}
           for law, nm in LAWNAME.items()}

    def rel_s(i): return set(golden[i]["relevant"])
    def rel_t(i):
        s = set(golden[i]["relevant"])
        for law in list(s): s |= fam.get(law, set())
        return s

    print("Nạp bge-m3 + Hybrid + Reranker (GPU)...", flush=True)
    r = HybridRetriever(use_rerank=True, embed_model="BAAI/bge-m3", collection="bge_m3",
                        segment=False, fp16=True)

    def run(ids):
        return [(dedup(r.search(golden[i]["q"], k=10, where=WHERE)), i) for i in ids]

    res = {}
    # không dùng từ điển
    r.expand = False
    nat = run(NAT); print("  xong NAT (no dict)", flush=True)
    smp = run(SAMPLE); print("  xong SAMPLE", flush=True)
    res["bgeHybrid_nat_strict"] = metrics([(d, rel_s(i)) for d, i in nat])
    res["bgeHybrid_nat_topic"] = metrics([(d, rel_t(i)) for d, i in nat])
    res["bgeHybrid_sample"] = metrics([(d, rel_s(i)) for d, i in smp])
    # + từ điển
    r.expand = True
    natd = run(NAT); print("  xong NAT (+dict)", flush=True)
    res["bgeHybrid_dict_nat_strict"] = metrics([(d, rel_s(i)) for d, i in natd])
    res["bgeHybrid_dict_nat_topic"] = metrics([(d, rel_t(i)) for d, i in natd])

    json.dump(res, open(os.path.join(os.path.dirname(__file__), "eval_bge_hybrid.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n=== bge-m3 + HYBRID + RERANKER ===")
    for k, v in res.items():
        print(f"  {k:26}", v)
    print("(so sánh PhoBERT+Hybrid+Rerank: câu mẫu Hit@1 0.650/MRR 0.764; câu TN 0.160/0.283)")
    print("✅ Lưu train/eval_bge_hybrid.json")


if __name__ == "__main__":
    main()
