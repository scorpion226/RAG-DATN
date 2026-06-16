# -*- coding: utf-8 -*-
"""Kiểm chứng reranker fine-tune: (1) có HẠI câu mẫu (formal) không?  (2) xác nhận test tự nhiên.
bge-m3 (+dict+sem cho TN) top-30 -> rerank PhoRanker fine-tune -> top-10. So no-rerank.
Chạy: python train/validate_reranker.py"""
import sys, os, json, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from pyvi import ViTokenizer
import chromadb, torch
from query_expand import expand_query

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
WHERE = {"effect_status": "In effect"}; KS = [1, 3, 5, 10]
DEV = "cuda" if torch.cuda.is_available() else "cpu"
FT = os.path.join(ROOT, "models", "ft-reranker-bge")
SAMPLE = [i for i, q in enumerate(golden) if q.get("type") in (None, "generated")][:200]
split = json.load(open(os.path.join(HERE, "ft_split.json"), encoding="utf-8"))  # chỉ để tham chiếu
# tái tạo test split của reranker (giống finetune_reranker)
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]
DOMAIN = {"15/2023/QH15": "KCB", "105/2016/QH13": "Duoc", "44/2024/QH15": "Duoc", "39/VBHN-VPQH": "Duoc",
          "55/2010/QH12": "ATTP", "61/VBHN-VPQH": "ATTP", "02/VBHN-VPQH": "ATTP", "46/2014/QH13": "BHYT",
          "51/2024/QH15": "BHYT", "09/2012/QH13": "TL", "08/VBHN-VPQH": "TL", "15/VBHN-VPQH": "TL",
          "11/VBHN-VPQH": "TL", "44/2019/QH14": "RB", "75/2006/QH11": "HM", "64/2006/QH11": "HIV",
          "33/VBHN-VPQH": "HIV", "114/2025/QH15": "PB"}


def dom(i):
    for dn in golden[i]["relevant"]:
        if dn in DOMAIN: return DOMAIN[dn]
    return "?"


def test_split():
    by = {}
    for i in NAT: by.setdefault(dom(i), []).append(i)
    te = []
    for d in sorted(by):
        ids = sorted(by[d]); nt = max(1, round(len(ids) * 0.3))
        step = len(ids) / nt; tp = {int(k * step) for k in range(nt)}
        for p, i in enumerate(ids):
            if p in tp: te.append(i)
    return sorted(te)


def metrics(items):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(items)
    for docs, rel in items:
        f = next((j + 1 for j, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / f) if f else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]): hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3), "n": n}


def dedup(x):
    s = []
    for dn in x:
        if dn and dn not in s: s.append(dn)
    return s


def main():
    bge = SentenceTransformer("BAAI/bge-m3", device=DEV)
    if DEV == "cuda": bge.half()
    bge.max_seq_length = 256
    coll = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db")).get_collection("bge_m3")
    lex = json.load(open(os.path.join(HERE, "lexicon.json"), encoding="utf-8"))
    lex_emb = np.load(os.path.join(HERE, "lexicon_emb.npy")).astype(np.float32)
    ce = CrossEncoder(FT, max_length=256, device=DEV)

    def sem(qv, K=3, tau=0.45):
        s = lex_emb @ np.asarray(qv, dtype=np.float32)
        return [lex[j] for j in np.argsort(-s)[:K] if s[j] >= tau]

    def cands(i, use_expand):
        q = golden[i]["q"]
        if use_expand:
            qv = bge.encode([q], normalize_embeddings=True)[0]
            qx = expand_query(q) + (" " + " ".join(sem(qv)) if sem(qv) else "")
        else:
            qx = q
        emb = bge.encode([qx], normalize_embeddings=True).tolist()
        r = coll.query(query_embeddings=emb, n_results=30, where=WHERE, include=["documents", "metadatas"])
        return q, [(d, m.get("document_number")) for d, m in zip(r["documents"][0], r["metadatas"][0])]

    def evalset(ids, use_expand):
        nr, rr = [], []
        for i in ids:
            q, cs = cands(i, use_expand); rel = set(golden[i]["relevant"])
            nr.append((dedup([dn for _, dn in cs]), rel))
            sq = ViTokenizer.tokenize(q)
            sc = ce.predict([[sq, ViTokenizer.tokenize(d)] for d, _ in cs])
            order = sorted(range(len(cs)), key=lambda j: sc[j], reverse=True)
            rr.append((dedup([cs[j][1] for j in order]), rel))
        return metrics(nr), metrics(rr)

    out = {}
    te = test_split()
    log = print
    log(">> CÂU MẪU (200 formal) — kiểm tra reranker fine-tune có HẠI không:")
    nr, rr = evalset(SAMPLE, use_expand=False)
    out["sample_norerank"] = nr; out["sample_ftrerank"] = rr
    log(f"   no-rerank: {nr}"); log(f"   ft-rerank: {rr}")
    log(">> CÂU TỰ NHIÊN TEST (69) — xác nhận lại:")
    nr2, rr2 = evalset(te, use_expand=True)
    out["nat_test_norerank"] = nr2; out["nat_test_ftrerank"] = rr2
    log(f"   no-rerank: {nr2}"); log(f"   ft-rerank: {rr2}")
    json.dump(out, open(os.path.join(HERE, "validate_reranker.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    log("✅ Lưu validate_reranker.json")


if __name__ == "__main__":
    main()
