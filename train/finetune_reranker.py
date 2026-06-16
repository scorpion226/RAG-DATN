# -*- coding: utf-8 -*-
"""HUẤN LUYỆN MÔ HÌNH cho RAG: fine-tune reranker bge-reranker-v2-m3 trên cặp
(câu đời thường → chunk luật ĐÚNG). Mục tiêu: dạy reranker ưu tiên luật gốc được gán nhãn
(trước đây reranker thô đẩy nghị định dưới luật lên → giảm Hit@1).
Tách 228 câu TN → train/test phân tầng theo lĩnh vực (deterministic). Đánh giá trên TEST giữ riêng.
Chạy: python train/finetune_reranker.py"""
import sys, os, json, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder, InputExample
from torch.utils.data import DataLoader
from pyvi import ViTokenizer
import chromadb, torch
from query_expand import expand_query

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rr_mine_cache.pkl")
RERANK_BASE = "itdainb/PhoRanker"   # 135M, vừa VRAM 8GB (bge-reranker-v2-m3 568M -> OOM)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]
WHERE = {"effect_status": "In effect"}; KS = [1, 3, 5, 10]
DEV = "cuda" if torch.cuda.is_available() else "cpu"
OUT_MODEL = os.path.join(ROOT, "models", "ft-reranker-bge")
DOMAIN = {"15/2023/QH15": "KCB", "105/2016/QH13": "Duoc", "44/2024/QH15": "Duoc", "39/VBHN-VPQH": "Duoc",
          "55/2010/QH12": "ATTP", "61/VBHN-VPQH": "ATTP", "02/VBHN-VPQH": "ATTP",
          "46/2014/QH13": "BHYT", "51/2024/QH15": "BHYT", "09/2012/QH13": "TL", "08/VBHN-VPQH": "TL",
          "15/VBHN-VPQH": "TL", "11/VBHN-VPQH": "TL", "44/2019/QH14": "RB", "75/2006/QH11": "HM",
          "64/2006/QH11": "HIV", "33/VBHN-VPQH": "HIV", "114/2025/QH15": "PB"}
LAWNAME = {"15/2023/QH15": "luật khám bệnh, chữa bệnh", "105/2016/QH13": "luật dược", "44/2024/QH15": "luật dược",
           "39/VBHN-VPQH": "luật dược", "55/2010/QH12": "luật an toàn thực phẩm", "61/VBHN-VPQH": "luật an toàn thực phẩm",
           "02/VBHN-VPQH": "luật an toàn thực phẩm", "46/2014/QH13": "luật bảo hiểm y tế", "51/2024/QH15": "luật bảo hiểm y tế",
           "09/2012/QH13": "phòng, chống tác hại của thuốc lá", "08/VBHN-VPQH": "phòng, chống tác hại của thuốc lá",
           "15/VBHN-VPQH": "phòng, chống tác hại của thuốc lá", "11/VBHN-VPQH": "phòng, chống tác hại của thuốc lá",
           "44/2019/QH14": "phòng, chống tác hại của rượu, bia", "75/2006/QH11": "hiến, lấy, ghép mô",
           "64/2006/QH11": "phòng, chống nhiễm vi rút gây ra hội chứng", "33/VBHN-VPQH": "phòng, chống nhiễm vi rút gây ra hội chứng",
           "114/2025/QH15": "luật phòng bệnh"}
MARK = ["hướng dẫn", "hợp nhất", "quy định chi tiết", "biện pháp thi hành", "quy định và biện pháp"]


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def dom(i):
    for dn in golden[i]["relevant"]:
        if dn in DOMAIN: return DOMAIN[dn]
    return "?"


def split_traintest():
    by = {}
    for i in NAT: by.setdefault(dom(i), []).append(i)
    tr, te = [], []
    for d in sorted(by):
        ids = sorted(by[d]); nt = max(1, round(len(ids) * 0.3))
        step = len(ids) / nt; tp = {int(k * step) for k in range(nt)}
        for p, i in enumerate(ids):
            (te if p in tp else tr).append(i)
    return sorted(tr), sorted(te)


def metrics(items):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(items)
    for docs, rel in items:
        f = next((j + 1 for j, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / f) if f else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]): hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3), "n": n}


def dedup(dns):
    s = []
    for dn in dns:
        if dn and dn not in s: s.append(dn)
    return s


def main():
    train_ids, test_ids = split_traintest()
    log(f"Split: {len(train_ids)} train / {len(test_ids)} test")

    # ---- mine (cache để khỏi chạy lại bge-m3) : raw (q, text, label) + test_cands ----
    if os.path.exists(CACHE):
        raw_pairs, test_cands = pickle.load(open(CACHE, "rb"))
        log(f"Nạp cache mining: {len(raw_pairs)} cặp, {len(test_cands)} câu test")
    else:
        bge = SentenceTransformer("BAAI/bge-m3", device=DEV)
        if DEV == "cuda": bge.half()
        bge.max_seq_length = 256
        coll = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db")).get_collection("bge_m3")
        lex = json.load(open(os.path.join(HERE, "lexicon.json"), encoding="utf-8"))
        lex_emb = np.load(os.path.join(HERE, "lexicon_emb.npy")).astype(np.float32)

        def sem(qv, K=3, tau=0.45):
            sims = lex_emb @ np.asarray(qv, dtype=np.float32)
            return [lex[j] for j in np.argsort(-sims)[:K] if sims[j] >= tau]

        def top30(i):
            q = golden[i]["q"]; qd = expand_query(q)
            qv = bge.encode([q], normalize_embeddings=True)[0]
            t = sem(qv); qx = qd + (" " + " ".join(t) if t else "")
            emb = bge.encode([qx], normalize_embeddings=True).tolist()
            r = coll.query(query_embeddings=emb, n_results=30, where=WHERE, include=["documents", "metadatas"])
            return [(d, m.get("document_number")) for d, m in zip(r["documents"][0], r["metadatas"][0])]

        log("Mining cặp train + candidate test (bge-m3)...")
        raw_pairs = []
        for i in train_ids:
            q = golden[i]["q"]; rel = set(golden[i]["relevant"]); cands = top30(i)
            pos = [d for d, dn in cands if dn in rel][:3]
            neg = [d for d, dn in cands if dn not in rel][:6]
            if not pos:
                try:
                    g = coll.get(where={"document_number": {"$in": list(rel)}}, limit=2, include=["documents"])
                    pos = g["documents"][:2]
                except Exception: pass
            for d in pos: raw_pairs.append((q, d, 1.0))
            for d in neg: raw_pairs.append((q, d, 0.0))
        test_cands = {i: top30(i) for i in test_ids}
        pickle.dump((raw_pairs, test_cands), open(CACHE, "wb"))
        log(f"Số cặp train: {len(raw_pairs)} | candidate test: {len(test_cands)} (đã cache)")
        del bge
        if DEV == "cuda": torch.cuda.empty_cache()

    # ---- train PhoRanker (135M, segment pyvi) ----
    log(f"Nạp {RERANK_BASE} + fine-tune (segment pyvi)...")
    examples = [InputExample(texts=[ViTokenizer.tokenize(q), ViTokenizer.tokenize(d)], label=lb)
                for q, d, lb in raw_pairs]
    ce = CrossEncoder(RERANK_BASE, num_labels=1, max_length=256, device=DEV)
    loader = DataLoader(examples, shuffle=True, batch_size=16)
    ce.fit(train_dataloader=loader, epochs=2, warmup_steps=max(1, len(loader) // 10),
           show_progress_bar=True)
    try:
        ce.save_pretrained(OUT_MODEL)
    except Exception:
        ce.model.save_pretrained(OUT_MODEL); ce.tokenizer.save_pretrained(OUT_MODEL)
    log(f"Đã lưu {OUT_MODEL} (tồn tại: {os.path.exists(os.path.join(OUT_MODEL, 'config.json'))})")

    # ---- eval test ----
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

    norerank, reranked = [], []
    for i in test_ids:
        cands = test_cands[i]; q = golden[i]["q"]; sq = ViTokenizer.tokenize(q)
        norerank.append((dedup([dn for _, dn in cands]), i))
        scores = ce.predict([[sq, ViTokenizer.tokenize(d)] for d, _ in cands])
        order = sorted(range(len(cands)), key=lambda j: scores[j], reverse=True)
        reranked.append((dedup([cands[j][1] for j in order]), i))

    res = {"no_rerank_strict": metrics([(d, rs(i)) for d, i in norerank]),
           "no_rerank_topic": metrics([(d, rt(i)) for d, i in norerank]),
           "ft_rerank_strict": metrics([(d, rs(i)) for d, i in reranked]),
           "ft_rerank_topic": metrics([(d, rt(i)) for d, i in reranked])}
    json.dump({"n_train": len(train_ids), "n_test": len(test_ids), "n_pairs": len(examples), "results": res},
              open(os.path.join(HERE, "finetune_reranker.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log(f"=== TEST {len(test_ids)} câu (bge-m3+dict+sem top-30 -> rerank) ===")
    for k, v in res.items(): log(f"  {k:22} {v}")
    log("✅ Lưu finetune_reranker.json")


if __name__ == "__main__":
    main()
