# -*- coding: utf-8 -*-
"""Thí nghiệm 6 — Query rewriting: dùng PhoGPT viết lại câu hỏi đời thường sang
ngôn ngữ pháp lý rồi truy xuất lại (Hybrid+Reranker). So 3 biến thể trên 30 câu tự nhiên:
  (a) baseline: câu gốc
  (b) rewrite : câu đã viết lại
  (c) combo   : câu gốc + câu viết lại (ghép)
Lưu eval/query_rewrite.json. Chạy: python eval/query_rewrite.py"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(HERE, "golden_questions.json"), encoding="utf-8"))
NAT = [q for q in golden if q.get("type") == "natural"]

from hybrid import HybridRetriever
from llm import PhoGPTGGUF

WHERE = {"effect_status": "In effect"}
KS = [1, 3, 5, 10]

REWRITE_PROMPT = """### Câu hỏi:
Hãy viết lại câu hỏi đời thường dưới đây thành MỘT câu hỏi trang trọng dùng đúng thuật ngữ trong văn bản quy phạm pháp luật Việt Nam (luật về y tế). Chỉ trả về câu hỏi viết lại, không giải thích.

Ví dụ:
- "Tôi muốn mở quán ăn nhỏ thì cần giấy gì?" -> "Điều kiện cấp Giấy chứng nhận cơ sở đủ điều kiện an toàn thực phẩm đối với cơ sở kinh doanh dịch vụ ăn uống là gì?"
- "Uống bia rồi lái xe có bị phạt không?" -> "Hành vi điều khiển phương tiện giao thông khi trong máu hoặc hơi thở có nồng độ cồn bị nghiêm cấm như thế nào theo Luật Phòng, chống tác hại của rượu, bia?"
- "Tôi muốn hiến thận cho người thân thì phải làm sao?" -> "Điều kiện và thủ tục đăng ký hiến mô, bộ phận cơ thể ở người sống được quy định như thế nào?"

Câu hỏi: {q}
### Trả lời:"""


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
    print(f"Câu tự nhiên: {len(NAT)} | Nạp retriever + PhoGPT...")
    r = HybridRetriever(use_rerank=True)
    gpt = PhoGPTGGUF(max_new_tokens=96)

    rows = {"baseline": [], "rewrite": [], "combo": []}
    log = []
    for i, it in enumerate(NAT):
        q = it["q"]; rel = set(it["relevant"])
        # viết lại
        out = gpt.llm(REWRITE_PROMPT.format(q=q), max_tokens=96, temperature=0.1,
                      top_p=0.95, repeat_penalty=1.1,
                      stop=["### Câu hỏi:", "\n-", "</s>"])
        rw = out["choices"][0]["text"].strip().strip('"').split("\n")[0].strip()
        if len(rw) < 12:           # viết lại hỏng -> giữ câu gốc
            rw = q
        combo = q + " " + rw
        for name, query in [("baseline", q), ("rewrite", rw), ("combo", combo)]:
            hits = r.search(query, k=10, where=WHERE)
            rows[name].append((docs_of(hits), rel))
        log.append({"q": q, "rewrite": rw})
        print(f"  [{i+1}/{len(NAT)}] {q[:42]} => {rw[:60]}")

    res = {name: metrics(v) for name, v in rows.items()}
    json.dump({"results": res, "rewrites": log},
              open(os.path.join(HERE, "query_rewrite.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("\n=== KẾT QUẢ (30 câu tự nhiên) ===")
    for name in ["baseline", "rewrite", "combo"]:
        print(f"  {name:9}", res[name])
    print("✅ Lưu query_rewrite.json")


if __name__ == "__main__":
    main()
