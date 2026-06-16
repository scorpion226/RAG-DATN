# -*- coding: utf-8 -*-
"""Thí nghiệm 9b — Fine-tune bi-encoder QUY MÔ LỚN (domain adaptation).

Sinh ~15k cặp (câu hỏi hình thức từ tiêu đề Điều, chunk chứa Điều đó) trên TOÀN CORPUS,
LOẠI TRỪ ~20 luật xuất hiện trong bộ eval câu tự nhiên -> 100 câu test sạch tuyệt đối
(đo khả năng KHÁI QUÁT, không phải ghi nhớ). MNRL, in-batch negatives, batch lớn.
Tiền xử lý ViTokenizer cho cả query lẫn chunk (khớp index). Lưu -> models/ft-bi-encoder-large/.
Chạy: python train/finetune_large.py
"""
import sys, os, re, json, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
random.seed(42)

import pyarrow.parquet as pq
from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

PARQUET = os.path.join(ROOT, "legal_medical_chunks_clean.parquet")
EMBED_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"
OUT_MODEL = os.path.join(ROOT, "models", "ft-bi-encoder-large")
MAX_PAIRS = 8000
MAX_SEQ = 128   # giới hạn độ dài để fine-tune khả thi trên CPU (attention O(L^2))

# Luật trong eval -> LOẠI khỏi dữ liệu huấn luyện (chống rò rỉ)
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
EVAL_LAWS = set()
for q in golden:
    if q.get("type") == "natural":
        EVAL_LAWS.update(q["relevant"])

STOP = ["phạm vi điều chỉnh", "đối tượng áp dụng", "giải thích từ ngữ", "hiệu lực thi hành",
        "tổ chức thực hiện", "quy định chuyển tiếp", "điều khoản thi hành", "sửa đổi",
        "bãi bỏ", "trách nhiệm thi hành", "áp dụng pháp luật", "nguyên tắc"]
RE = re.compile(r"Điều\s+\d+[\.:]?\s+([A-ZÀ-ỸĐ][^\n]{6,110})")
TEMPLATES = [lambda t: f"Pháp luật quy định như thế nào về {t[0].lower()+t[1:]}?",
             lambda t: f"{t} được quy định ra sao?",
             lambda t: f"Nội dung quy định về {t[0].lower()+t[1:]} là gì?"]


def clean_title(t):
    return re.split(r"\d", t)[0].strip().rstrip(".,;:").strip()


def main():
    print(f"Loại {len(EVAL_LAWS)} luật eval khỏi train. Quét corpus sinh cặp...", flush=True)
    pairs = []
    pf = pq.ParquetFile(PARQUET)
    scanned = 0
    for b in pf.iter_batches(columns=["document_number", "text"], batch_size=8000):
        d = b.to_pydict()
        for dn, t in zip(d["document_number"], d["text"]):
            scanned += 1
            if dn in EVAL_LAWS:            # chống rò rỉ
                continue
            m = RE.search(t)               # tiêu đề Điều đầu tiên trong chunk
            if not m:
                continue
            ti = clean_title(m.group(1))
            low = ti.lower()
            if len(ti) < 10 or ti.isupper() or any(s in low for s in STOP):
                continue
            q = random.choice(TEMPLATES)(ti)
            pairs.append((q, t))
        if len(pairs) >= MAX_PAIRS * 3:
            break
    random.shuffle(pairs)
    pairs = pairs[:MAX_PAIRS]
    print(f"Quét {scanned:,} chunk -> {len(pairs):,} cặp huấn luyện", flush=True)

    print("Nạp model gốc, tách từ, dựng InputExample...", flush=True)
    examples = [InputExample(texts=[ViTokenizer.tokenize(q), ViTokenizer.tokenize(c)])
                for q, c in pairs]
    model = SentenceTransformer(EMBED_MODEL, device="cpu")
    model.max_seq_length = MAX_SEQ
    loader = DataLoader(examples, shuffle=True, batch_size=32)
    loss = losses.MultipleNegativesRankingLoss(model)
    steps = len(loader)
    print(f"Fine-tune: 1 epoch, {steps} step (CPU)...", flush=True)
    model.fit(train_objectives=[(loader, loss)], epochs=1,
              warmup_steps=max(1, steps // 10), show_progress_bar=True,
              output_path=OUT_MODEL)
    print(f"✅ Lưu -> {OUT_MODEL}", flush=True)


if __name__ == "__main__":
    main()
