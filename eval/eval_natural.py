# -*- coding: utf-8 -*-
"""So sánh hiệu năng trên câu DIỄN ĐẠT TỰ NHIÊN vs câu mẫu (Hybrid+Reranker).
Chạy: python eval/eval_natural.py  -> in bảng + lưu eval/eval_natural.json"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
from hybrid import HybridRetriever

WHERE = {"effect_status": "In effect"}
KS = [1, 3, 5, 10]


def docs_of(hits):
    seen = []
    for h in hits:
        dn = h["metadata"].get("document_number")
        if dn and dn not in seen:
            seen.append(dn)
    return seen


def metrics(rows):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(rows)
    for docs, rel in rows:
        first = next((i + 1 for i, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]):
                hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3), "n": n}


def main():
    nat = [q for q in golden if q.get("type") == "natural"]
    print(f"Câu tự nhiên: {len(nat)} — đánh giá Hybrid+Reranker...")
    r = HybridRetriever(use_rerank=True)
    rows = []; misses = []
    for i, it in enumerate(nat):
        hits = r.search(it["q"], k=10, where=WHERE)
        docs = docs_of(hits)
        rel = set(it["relevant"])
        rows.append((docs, rel))
        first = next((i2 + 1 for i2, dn in enumerate(docs) if dn in rel), None)
        if not first or first > 3:
            misses.append({"q": it["q"], "rank": first, "top1": docs[0] if docs else None})
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(nat)}")
    m_nat = metrics(rows)
    out = {"natural": m_nat, "templated_ref": "xem eval200.json (200 câu)",
           "hard_cases": misses}
    json.dump(out, open(os.path.join(HERE, "eval_natural.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n=== Câu TỰ NHIÊN (30 câu, Hybrid+Reranker) ===")
    print(" ", m_nat)
    print("Các câu khó (rank>3 hoặc MISS):")
    for m in misses:
        print(f"  [{m['rank'] or 'MISS'}] {m['q'][:60]} → top1: {m['top1']}")
    print("✅ Lưu eval_natural.json")


if __name__ == "__main__":
    main()
