# -*- coding: utf-8 -*-
"""GROUP K-FOLD theo LUẬT/lĩnh vực (leave-one-domain-out) cho reranker — kiểm chứng định lượng
nghi ngờ "reranker học theo quy ước nhãn" (góp ý GVHD). Khác cv_reranker.py (chia theo CÂU):
ở đây MỖI fold test là 1 lĩnh vực, train trên các lĩnh vực CÒN LẠI → KHÔNG luật nào xuất hiện
ở cả train lẫn test. Nếu Hit@1 vẫn cao → loại trừ memorization; nếu giảm mạnh → đúng là shortcut.
Tái dùng cache candidate cv_cands.pkl. Chạy: python train/cv_reranker_bylaw.py"""
import sys, os, json, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
from sentence_transformers import CrossEncoder, InputExample
from torch.utils.data import DataLoader
from pyvi import ViTokenizer
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]
KS = [1, 3, 5, 10]; DEV = "cuda" if torch.cuda.is_available() else "cpu"
CANDS = os.path.join(HERE, "cv_cands.pkl")
DOMAIN = {"15/2023/QH15": "KCB", "105/2016/QH13": "Duoc", "44/2024/QH15": "Duoc", "39/VBHN-VPQH": "Duoc",
          "55/2010/QH12": "ATTP", "61/VBHN-VPQH": "ATTP", "02/VBHN-VPQH": "ATTP", "46/2014/QH13": "BHYT",
          "51/2024/QH15": "BHYT", "09/2012/QH13": "TL", "08/VBHN-VPQH": "TL", "15/VBHN-VPQH": "TL",
          "11/VBHN-VPQH": "TL", "44/2019/QH14": "RB", "75/2006/QH11": "HM", "64/2006/QH11": "HIV",
          "33/VBHN-VPQH": "HIV", "114/2025/QH15": "PB"}


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)
def dom(i):
    for dn in golden[i]["relevant"]:
        if dn in DOMAIN: return DOMAIN[dn]
    return "?"
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
    cands = pickle.load(open(CANDS, "rb"))
    by = {}
    for i in NAT: by.setdefault(dom(i), []).append(i)
    domains = sorted(by)
    log(f"Leave-one-domain-out: {len(domains)} lĩnh vực {domains}")
    per = []
    jpath = os.path.join(HERE, "cv_reranker_bylaw.json")
    if os.path.exists(jpath):
        old = json.load(open(jpath, encoding="utf-8"))
        per = old if isinstance(old, list) else old.get("per_fold", [])
    done = {p["domain"] for p in per}
    for d in domains:
        if d in done: continue
        test_ids = by[d]; train_ids = [i for dd in domains if dd != d for i in by[dd]]
        ex = []
        for i in train_ids:
            q = golden[i]["q"]; rel = set(golden[i]["relevant"])
            pos = [t for t, dn in cands[i] if dn in rel][:3]
            neg = [t for t, dn in cands[i] if dn not in rel][:6]
            for t in pos: ex.append(InputExample(texts=[ViTokenizer.tokenize(q), ViTokenizer.tokenize(t)], label=1.0))
            for t in neg: ex.append(InputExample(texts=[ViTokenizer.tokenize(q), ViTokenizer.tokenize(t)], label=0.0))
        ce = CrossEncoder("itdainb/PhoRanker", num_labels=1, max_length=256, device=DEV)
        ce.fit(train_dataloader=DataLoader(ex, shuffle=True, batch_size=16),
               epochs=2, warmup_steps=max(1, len(ex)//160), show_progress_bar=False)
        nr, rr = [], []
        for i in test_ids:
            cs = cands[i]; rel = set(golden[i]["relevant"]); sq = ViTokenizer.tokenize(golden[i]["q"])
            nr.append((dedup([dn for _, dn in cs]), rel))
            sc = ce.predict([[sq, ViTokenizer.tokenize(t)] for t, _ in cs])
            order = sorted(range(len(cs)), key=lambda j: sc[j], reverse=True)
            rr.append((dedup([cs[j][1] for j in order]), rel))
        m_nr = metrics(nr); m_rr = metrics(rr)
        per.append({"domain": d, "n_test": len(test_ids), "norerank": m_nr, "ftrerank": m_rr})
        log(f"{d:8} test={len(test_ids):3} | no-rr Hit@1={m_nr['Hit@1']} | ft Hit@1={m_rr['Hit@1']} MRR={m_rr['MRR']}")
        json.dump(per, open(jpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        del ce
        if DEV == "cuda": torch.cuda.empty_cache()
    h1 = [p["ftrerank"]["Hit@1"] for p in per]; mr = [p["ftrerank"]["MRR"] for p in per]
    summary = {"n_folds": len(per), "split": "group-by-domain (leave-one-out)",
               "ftrerank_Hit@1_mean_std": [round(np.mean(h1), 3), round(np.std(h1), 3)],
               "ftrerank_MRR_mean_std": [round(np.mean(mr), 3), round(np.std(mr), 3)],
               "norerank_Hit@1_mean": round(np.mean([p["norerank"]["Hit@1"] for p in per]), 3)}
    json.dump({"summary": summary, "per_fold": per}, open(jpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    log("=== SUMMARY (group-by-law) ===")
    for k, v in summary.items(): log(f"  {k}: {v}")
    log("✅ Lưu cv_reranker_bylaw.json")


if __name__ == "__main__":
    main()
