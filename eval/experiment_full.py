# -*- coding: utf-8 -*-
"""
experiment_full.py — Thực nghiệm tổng hợp cho báo cáo:
  (1) Precision@k, Recall@k, F1@k (mức văn bản) — đánh giá độ chính xác truy xuất.
  (2) Ảnh hưởng số nguồn k.
  (3) Thời gian phản hồi: truy xuất vs sinh.
  (4) Chất lượng câu trả lời + mức độ trích dẫn (chạy PhoGPT trên một số câu).
Kết quả lưu eval/experiment_results.json để vẽ biểu đồ & lập bảng.
Chạy: python eval/experiment_full.py
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
KS = [1, 3, 5, 10]
GEN_SUBSET = 6   # số câu chạy PhoGPT để đánh giá chất lượng/độ trễ sinh

from hybrid import HybridRetriever
from rag_core import format_context


def ranked_docs(hits):
    seen = []
    for h in hits:
        dn = h["metadata"].get("document_number")
        if dn and dn not in seen:
            seen.append(dn)
    return seen


def main():
    print("Nạp retriever (hybrid + reranker)...")
    r = HybridRetriever(use_rerank=True)

    # ---------- (1)+(2)+(3a) Precision/Recall@k + thời gian truy xuất ----------
    prec = {k: 0.0 for k in KS}; rec = {k: 0.0 for k in KS}
    retr_times = []
    per_q = []
    print("Đo truy xuất trên", len(golden), "câu...")
    for it in golden:
        t = time.time()
        hits = r.search(it["q"], k=10, where={"effect_status": "In effect"})
        dt = time.time() - t
        retr_times.append(dt)
        docs = ranked_docs(hits)
        rel = set(it["relevant"])
        first = next((i + 1 for i, dn in enumerate(docs) if dn in rel), None)
        for k in KS:
            inter = len(set(docs[:k]) & rel)
            prec[k] += inter / k
            rec[k] += inter / len(rel)
        per_q.append({"q": it["q"], "top": docs[0] if docs else None,
                      "rank": first, "retr_s": round(dt, 2)})
    n = len(golden)
    pr = {k: {"P": round(prec[k] / n, 3), "R": round(rec[k] / n, 3)} for k in KS}
    for k in KS:
        p, rc = pr[k]["P"], pr[k]["R"]
        pr[k]["F1"] = round(2 * p * rc / (p + rc), 3) if (p + rc) else 0.0
    avg_retr = round(sum(retr_times) / len(retr_times), 2)
    print("Precision/Recall/F1@k:", pr)
    print("Thời gian truy xuất TB:", avg_retr, "s")

    # ---------- (4)+(3b) Sinh câu trả lời: chất lượng, trích dẫn, độ trễ ----------
    print(f"\nNạp PhoGPT, sinh {GEN_SUBSET} câu để đánh giá chất lượng/độ trễ...")
    from llm import PhoGPTGGUF
    llm = PhoGPTGGUF()
    gen = []
    for it in golden[:GEN_SUBSET]:
        hits = r.search(it["q"], k=5, where={"effect_status": "In effect"})
        ctx = format_context(hits)
        t = time.time()
        ans = llm.generate(it["q"], ctx, hits=hits)
        gt = time.time() - t
        srcs = ranked_docs(hits)
        rel = set(it["relevant"])
        cite_ok = any(dn in rel for dn in srcs)
        gen.append({"q": it["q"], "answer": ans.strip()[:300],
                    "sources": srcs[:5], "cite_ok": cite_ok, "gen_s": round(gt, 1)})
        print(f"  [{('cite OK' if cite_ok else 'cite?'):8}] {gt:4.0f}s | {it['q'][:50]}")
    avg_gen = round(sum(g["gen_s"] for g in gen) / len(gen), 1)
    cite_rate = round(sum(g["cite_ok"] for g in gen) / len(gen), 3)

    out = {"precision_recall": pr, "avg_retrieval_s": avg_retr,
           "avg_gen_s": avg_gen, "cite_rate": cite_rate,
           "per_question": per_q, "generation": gen, "n": n}
    json.dump(out, open(os.path.join(HERE, "experiment_results.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n✅ Lưu experiment_results.json | gen TB {avg_gen}s | tỉ lệ trích dẫn đúng {cite_rate}")


if __name__ == "__main__":
    main()
