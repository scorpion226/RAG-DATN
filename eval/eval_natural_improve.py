# -*- coding: utf-8 -*-
"""Thí nghiệm 8 — Cải thiện câu hỏi diễn đạt tự nhiên. So 4 điều kiện trên 100 câu type=natural,
cấu hình truy xuất Hybrid + Reranker:
  (a) baseline : câu gốc
  (b) dict     : câu gốc + thuật ngữ pháp lý từ TỪ ĐIỂN ánh xạ (query_expand.expand_query)
  (c) hyde     : câu gốc + ĐOẠN GIẢ ĐỊNH do PhoGPT sinh (Hypothetical Document Embeddings)
  (d) dict+hyde: kết hợp cả hai
RESUME ĐƯỢC (ghi từng câu vào eval/eval_natural_improve.jsonl). Nên chạy DETACHED.
Chạy: python eval/eval_natural_improve.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
NAT = [(i, q) for i, q in enumerate(golden) if q.get("type") == "natural"]
JSONL = os.path.join(HERE, "eval_natural_improve.jsonl")
WHERE = {"effect_status": "In effect"}

from query_expand import expand_query
from hybrid import HybridRetriever
from llm import PhoGPTGGUF

# Prompt sinh ĐOẠN GIẢ ĐỊNH (HyDE): yêu cầu mô hình viết một đoạn ngắn theo VĂN PHONG pháp lý
# trả lời câu hỏi — đoạn này CHỈ dùng để embed truy xuất (không hiển thị, không parse trích dẫn),
# nên kể cả nếu mô hình bịa chi tiết, các THUẬT NGỮ pháp lý trong đoạn vẫn giúp khớp đúng văn bản.
HYDE_PROMPT = """### Câu hỏi:
Hãy viết MỘT đoạn văn ngắn (3-4 câu) theo văn phong văn bản quy phạm pháp luật Việt Nam về y tế để trả lời câu hỏi dưới đây. Dùng đúng thuật ngữ pháp lý. Chỉ viết đoạn văn, không liệt kê, không mở đầu.

Câu hỏi: {q}
### Trả lời:"""


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
            try:
                done.add(json.loads(line)["idx"])
            except Exception:
                pass
    print(f"Đã xong {len(done)}/{len(NAT)} câu tự nhiên. Nạp retriever + PhoGPT...", flush=True)
    r = HybridRetriever(use_rerank=True)
    gpt = PhoGPTGGUF(max_new_tokens=160)

    with open(JSONL, "a", encoding="utf-8") as f:
        for n, (gi, it) in enumerate(NAT):
            if gi in done:
                continue
            q = it["q"]
            # Sinh đoạn giả định (HyDE)
            out = gpt.llm(HYDE_PROMPT.format(q=q), max_tokens=160, temperature=0.2,
                          top_p=0.95, repeat_penalty=1.1,
                          stop=["### Câu hỏi:", "</s>", "<|endoftext|>"])
            hyde = out["choices"][0]["text"].strip().replace("\n", " ")
            if len(hyde) < 10:
                hyde = q
            q_dict = expand_query(q)
            queries = {
                "baseline": q,
                "dict": q_dict,
                "hyde": q + " " + hyde,
                "dict_hyde": q_dict + " " + hyde,
            }
            rec = {"idx": gi, "hyde_text": hyde}
            for name, query in queries.items():
                hits = r.search(query, k=10, where=WHERE)
                rec[name] = docs_of(hits)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  [{n+1}/{len(NAT)}] {q[:40]}", flush=True)
    print("✅ Hoàn tất. Chạy: python eval/aggregate_natural_improve.py", flush=True)


if __name__ == "__main__":
    main()
