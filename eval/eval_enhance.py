# -*- coding: utf-8 -*-
"""Đo các kỹ thuật mở rộng/chuẩn hóa truy vấn deterministic trên 100 câu tự nhiên
(cấu hình Hybrid + Reranker). Tất cả đặt TRÊN NỀN từ điển ánh xạ (expand_query):
  dict                : expand_query(q)                         [đã có ~0.230]
  dict+norm+mined     : + chuẩn hóa viết tắt (#3) + glossary (#1)
  dict+rm3            : + pseudo-relevance feedback (#2)
  dict+rm3+norm+mined : full stack
RESUME được (eval/eval_enhance.jsonl). Chạy DETACHED.
Chạy: python eval/eval_enhance.py"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]
JSONL = os.path.join(HERE, "eval_enhance.jsonl")
WHERE = {"effect_status": "In effect"}

from hybrid import HybridRetriever
from query_expand import expand_query
from enhance import normalize_query, mined_expand, rm3_expand


def docs_of(hits):
    seen = []
    for h in hits:
        dn = h["metadata"].get("document_number")
        if dn and dn not in seen:
            seen.append(dn)
    return seen


def main():
    done = set()
    if os.path.exists(JSONL):
        for line in open(JSONL, encoding="utf-8"):
            try: done.add(json.loads(line)["idx"])
            except Exception: pass
    print(f"Đã xong {len(done)}/{len(NAT)}. Nạp retriever...", flush=True)
    r = HybridRetriever(use_rerank=True)
    reranker = r.reranker

    with open(JSONL, "a", encoding="utf-8") as f:
        for n, i in enumerate(NAT):
            if i in done:
                continue
            q = golden[i]["q"]
            qd = expand_query(q)                       # nền: từ điển ánh xạ
            # vòng feedback RM3: hybrid KHÔNG rerank, top-5
            r.reranker = None
            fb = r.search(qd, k=5, where=WHERE)
            r.reranker = reranker
            fb_texts = [h.get("text") or "" for h in fb]
            q_dm = mined_expand(normalize_query(qd))   # #3 + #1
            q_rm3 = rm3_expand(qd, fb_texts)           # #2
            q_full = rm3_expand(mined_expand(normalize_query(qd)), fb_texts)
            rec = {"idx": i}
            for name, query in [("dict_norm_mined", q_dm), ("dict_rm3", q_rm3),
                                ("dict_rm3_norm_mined", q_full)]:
                rec[name] = docs_of(r.search(query, k=10, where=WHERE))
            f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
            print(f"  [{n+1}/{len(NAT)}] {q[:38]}", flush=True)
    print("✅ Hoàn tất. Chạy: python eval/aggregate_enhance.py", flush=True)


if __name__ == "__main__":
    main()
