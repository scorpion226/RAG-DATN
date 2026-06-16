# -*- coding: utf-8 -*-
"""Tinh chỉnh MỊN K/τ quanh điểm tốt (lexicon v1 = tiêu đề Điều, man+sem).
Grid K∈{2,3,4} × τ∈{0.30,0.35,0.40,0.45,0.50}. Train(71)/Test(29), báo cáo full(100).
Chạy: python train/dict_finetune.py"""
import sys, os, json, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from sentence_transformers import SentenceTransformer
import chromadb, torch
from query_expand import expand_query

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
split = json.load(open(os.path.join(HERE, "ft_split.json"), encoding="utf-8"))
TRAIN, TEST = set(split["train"]), set(split["test"])
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


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def metrics(items):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(items)
    for docs, rel in items:
        first = next((i + 1 for i, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]): hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3), "n": n}


def main():
    bge = SentenceTransformer("BAAI/bge-m3", device=DEV)
    if DEV == "cuda": bge.half()
    bge.max_seq_length = 256
    coll = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db")).get_collection("bge_m3")
    lex = json.load(open(os.path.join(HERE, "lexicon.json"), encoding="utf-8"))
    lex_emb = np.load(os.path.join(HERE, "lexicon_emb.npy")).astype(np.float32)
    log(f"Lexicon v1: {len(lex)}")

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

    qtext = {i: golden[i]["q"] for i in NAT}
    qraw = {i: np.asarray(bge.encode([qtext[i]], normalize_embeddings=True)[0], dtype=np.float32) for i in NAT}
    sims_cache = {i: lex_emb @ qraw[i] for i in NAT}

    def retrieve(query):
        emb = bge.encode([query], normalize_embeddings=True).tolist()
        r = coll.query(query_embeddings=emb, n_results=15, where=WHERE, include=["metadatas"])
        seen = []
        for m in r["metadatas"][0]:
            dn = m.get("document_number")
            if dn and dn not in seen: seen.append(dn)
        return seen

    results = {}
    for K in (2, 3, 4):
        for tau in (0.30, 0.35, 0.40, 0.45, 0.50):
            da = {}
            for i in NAT:
                sims = sims_cache[i]
                terms = [lex[j] for j in np.argsort(-sims)[:K] if sims[j] >= tau]
                q = expand_query(qtext[i]) + (" " + " ".join(terms) if terms else "")
                da[i] = retrieve(q)
            name = f"K{K}_t{tau}"
            results[name] = {
                "train_strict": metrics([(da[i], rs(i)) for i in NAT if i in TRAIN]),
                "test_strict": metrics([(da[i], rs(i)) for i in NAT if i in TEST]),
                "full_strict": metrics([(da[i], rs(i)) for i in NAT]),
                "full_topic": metrics([(da[i], rt(i)) for i in NAT])}
            r = results[name]
            log(f"{name:10} train={r['train_strict']['Hit@1']} test={r['test_strict']['Hit@1']} "
                f"full={r['full_strict']['Hit@1']} MRR={r['full_strict']['MRR']} topicH10={r['full_topic']['Hit@10']}")
            json.dump(results, open(os.path.join(HERE, "dict_finetune.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
    best = max(results, key=lambda c: (results[c]["train_strict"]["MRR"], results[c]["train_strict"]["Hit@1"]))
    log(f"==> BEST theo train: {best} | test {results[best]['test_strict']} | full {results[best]['full_strict']} | topic {results[best]['full_topic']}")
    json.dump({"best_by_train": best, "all": results},
              open(os.path.join(HERE, "dict_finetune.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log("✅ Lưu dict_finetune.json")


if __name__ == "__main__":
    main()
