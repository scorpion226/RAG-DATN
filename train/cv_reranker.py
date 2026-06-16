# -*- coding: utf-8 -*-
"""5-FOLD CROSS-VALIDATION cho reranker fine-tune (PhoRanker) trên 228 câu tự nhiên.
Mine candidate top-30 (bge-m3+dict+sem) cho TẤT CẢ 228 câu MỘT lần (cache), rồi mỗi fold:
train PhoRanker trên 4/5, đo trên 1/5 giữ riêng. Báo cáo mean±std → kiểm chứng 0.81 không do may split.
Chạy: python train/cv_reranker.py"""
import sys, os, json, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder, InputExample
from torch.utils.data import DataLoader
from pyvi import ViTokenizer
import chromadb, torch
from query_expand import expand_query

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]
WHERE = {"effect_status": "In effect"}; KS = [1, 3, 5, 10]
DEV = "cuda" if torch.cuda.is_available() else "cpu"
CANDS = os.path.join(HERE, "cv_cands.pkl")
NFOLD = 5
DOMAIN = {"15/2023/QH15": "KCB", "105/2016/QH13": "Duoc", "44/2024/QH15": "Duoc", "39/VBHN-VPQH": "Duoc",
          "55/2010/QH12": "ATTP", "61/VBHN-VPQH": "ATTP", "02/VBHN-VPQH": "ATTP", "46/2014/QH13": "BHYT",
          "51/2024/QH15": "BHYT", "09/2012/QH13": "TL", "08/VBHN-VPQH": "TL", "15/VBHN-VPQH": "TL",
          "11/VBHN-VPQH": "TL", "44/2019/QH14": "RB", "75/2006/QH11": "HM", "64/2006/QH11": "HIV",
          "33/VBHN-VPQH": "HIV", "114/2025/QH15": "PB"}
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


def folds():
    by = {}
    for i in NAT: by.setdefault(dom(i), []).append(i)
    fmap = {f: [] for f in range(NFOLD)}
    for d in sorted(by):
        for p, i in enumerate(sorted(by[d])):
            fmap[p % NFOLD].append(i)
    return fmap


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


def build_cands():
    bge = SentenceTransformer("BAAI/bge-m3", device=DEV)
    if DEV == "cuda": bge.half()
    bge.max_seq_length = 256
    coll = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db")).get_collection("bge_m3")
    lex = json.load(open(os.path.join(HERE, "lexicon.json"), encoding="utf-8"))
    lex_emb = np.load(os.path.join(HERE, "lexicon_emb.npy")).astype(np.float32)

    def sem(qv):
        s = lex_emb @ np.asarray(qv, dtype=np.float32)
        return [lex[j] for j in np.argsort(-s)[:3] if s[j] >= 0.45]

    cands = {}
    for n, i in enumerate(NAT):
        q = golden[i]["q"]; qv = bge.encode([q], normalize_embeddings=True)[0]
        qx = expand_query(q) + (" " + " ".join(sem(qv)) if sem(qv) else "")
        emb = bge.encode([qx], normalize_embeddings=True).tolist()
        r = coll.query(query_embeddings=emb, n_results=30, where=WHERE, include=["documents", "metadatas"])
        cands[i] = [(d, m.get("document_number")) for d, m in zip(r["documents"][0], r["metadatas"][0])]
        if (n + 1) % 50 == 0: log(f"  mine {n+1}/{len(NAT)}")
    pickle.dump(cands, open(CANDS, "wb"))
    del bge
    if DEV == "cuda": torch.cuda.empty_cache()
    return cands


def main():
    cands = pickle.load(open(CANDS, "rb")) if os.path.exists(CANDS) else build_cands()
    log(f"Candidates: {len(cands)} câu")
    fmap = folds()
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

    # RESUME: nạp fold đã xong (nếu chạy lại sau khi bị kill)
    per_fold = []
    jpath = os.path.join(HERE, "cv_reranker.json")
    if os.path.exists(jpath):
        try:
            old = json.load(open(jpath, encoding="utf-8"))
            per_fold = old if isinstance(old, list) else old.get("per_fold", [])
        except Exception:
            per_fold = []
    done = {pf["fold"] for pf in per_fold}
    if done: log(f"Resume: đã có fold {sorted(done)}")
    for f in range(NFOLD):
        if f in done:
            continue
        test_ids = fmap[f]; train_ids = [i for ff in range(NFOLD) if ff != f for i in fmap[ff]]
        examples = []
        for i in train_ids:
            q = golden[i]["q"]; rel = rs(i)
            pos = [d for d, dn in cands[i] if dn in rel][:3]
            neg = [d for d, dn in cands[i] if dn not in rel][:6]
            for d in pos: examples.append(InputExample(texts=[ViTokenizer.tokenize(q), ViTokenizer.tokenize(d)], label=1.0))
            for d in neg: examples.append(InputExample(texts=[ViTokenizer.tokenize(q), ViTokenizer.tokenize(d)], label=0.0))
        ce = CrossEncoder("itdainb/PhoRanker", num_labels=1, max_length=256, device=DEV)
        loader = DataLoader(examples, shuffle=True, batch_size=16)
        ce.fit(train_dataloader=loader, epochs=2, warmup_steps=max(1, len(loader) // 10), show_progress_bar=False)
        nr, rr = [], []
        for i in test_ids:
            cs = cands[i]; sq = ViTokenizer.tokenize(golden[i]["q"])
            nr.append((dedup([dn for _, dn in cs]), i))
            sc = ce.predict([[sq, ViTokenizer.tokenize(d)] for d, _ in cs])
            order = sorted(range(len(cs)), key=lambda j: sc[j], reverse=True)
            rr.append((dedup([cs[j][1] for j in order]), i))
        m_nr_s = metrics([(d, rs(i)) for d, i in nr]); m_rr_s = metrics([(d, rs(i)) for d, i in rr])
        m_rr_t = metrics([(d, rt(i)) for d, i in rr])
        per_fold.append({"fold": f, "n_test": len(test_ids), "norerank_strict": m_nr_s,
                         "ftrerank_strict": m_rr_s, "ftrerank_topic": m_rr_t})
        log(f"Fold {f}: test={len(test_ids)} | no-rr Hit@1={m_nr_s['Hit@1']} | ft Hit@1={m_rr_s['Hit@1']} MRR={m_rr_s['MRR']} | topic Hit@10={m_rr_t['Hit@10']}")
        json.dump(per_fold, open(os.path.join(HERE, "cv_reranker.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        del ce
        if DEV == "cuda": torch.cuda.empty_cache()

    def ms(key, sub):
        vals = [pf[key][sub] for pf in per_fold]
        return round(float(np.mean(vals)), 3), round(float(np.std(vals)), 3)
    summary = {"n_folds": NFOLD,
               "ftrerank_strict_Hit@1": ms("ftrerank_strict", "Hit@1"),
               "ftrerank_strict_MRR": ms("ftrerank_strict", "MRR"),
               "ftrerank_topic_Hit@10": ms("ftrerank_topic", "Hit@10"),
               "norerank_strict_Hit@1": ms("norerank_strict", "Hit@1")}
    json.dump({"summary": summary, "per_fold": per_fold},
              open(os.path.join(HERE, "cv_reranker.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log("=== CV SUMMARY (mean±std) ===")
    for k, v in summary.items():
        if k != "n_folds": log(f"  {k}: {v[0]} ± {v[1]}")
    log("✅ Lưu cv_reranker.json")


if __name__ == "__main__":
    main()
