# -*- coding: utf-8 -*-
"""Quét Precision/Recall/F1 ở dải k = 1..10 (mức văn bản, Hybrid+Reranker) trên bộ 50 câu.
Lưu eval/pr_sweep.json. Chỉ truy xuất (không sinh) nên nhanh."""
import sys, os, json, statistics
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
from hybrid import HybridRetriever

KS = list(range(1, 11))


def ranked_docs(hits):
    seen = []
    for h in hits:
        dn = h["metadata"].get("document_number")
        if dn and dn not in seen:
            seen.append(dn)
    return seen


def main():
    print("Nạp retriever (hybrid+rerank)...")
    r = HybridRetriever(use_rerank=True)
    ranked_all = []
    for i, it in enumerate(golden):
        hits = r.search(it["q"], k=10, where={"effect_status": "In effect"})
        ranked_all.append((ranked_docs(hits), set(it["relevant"])))
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(golden)}")
    rows = {}
    for k in KS:
        P = R = 0.0
        for docs, rel in ranked_all:
            inter = len(set(docs[:k]) & rel)
            P += inter / k
            R += inter / len(rel)
        P /= len(golden); R /= len(golden)
        F1 = (2 * P * R / (P + R)) if (P + R) else 0.0
        rows[k] = {"P": round(P, 3), "R": round(R, 3), "F1": round(F1, 3)}
    avg_rel = statistics.mean(len(it["relevant"]) for it in golden)
    for k in KS:
        rows[k]["ceilP"] = round(min(avg_rel, k) / k, 3)
    json.dump({"sweep": rows, "avg_rel": round(avg_rel, 2), "n": len(golden)},
              open(os.path.join(HERE, "pr_sweep.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\nk  | P     R     F1    | trầnP  | đạt%")
    for k in KS:
        v = rows[k]; att = v["P"] / v["ceilP"] * 100 if v["ceilP"] else 0
        print(f"{k:>2} | {v['P']:.3f} {v['R']:.3f} {v['F1']:.3f} | {v['ceilP']:.3f} | {att:.0f}%")
    print("✅ Lưu pr_sweep.json")


if __name__ == "__main__":
    main()
