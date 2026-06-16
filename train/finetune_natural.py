# -*- coding: utf-8 -*-
"""Thí nghiệm 9 (proof-of-concept) — Fine-tune bi-encoder cho câu đời thường -> luật.

QUY TRÌNH TRUNG THỰC:
  - Tách 100 câu tự nhiên -> 70 TRAIN / 30 TEST, PHÂN TẦNG theo lĩnh vực, hạt giống CỐ ĐỊNH.
    KHÔNG huấn luyện trên câu dùng để đo (tránh rò rỉ dữ liệu).
  - Cặp huấn luyện: (câu train, chunk LIÊN QUAN NHẤT trong luật đúng) — hard-positive mining
    bằng cách vector-search giới hạn trong các luật được gán nhãn của câu đó.
  - Loss: MultipleNegativesRankingLoss (in-batch negatives).
  - Tiền xử lý: ViTokenizer.tokenize cho CẢ query lẫn chunk (khớp phân phối index).
Lưu model -> models/ft-bi-encoder/ và split -> train/ft_split.json.
Chạy: python train/finetune_natural.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))

from pyvi import ViTokenizer
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader
import chromadb

EMBED_MODEL = "bkai-foundation-models/vietnamese-bi-encoder"
CHROMA_DIR = os.path.join(ROOT, "chroma_db"); COLLECTION = "legal_medical"
OUT_MODEL = os.path.join(ROOT, "models", "ft-bi-encoder")
SPLIT_JSON = os.path.join(HERE, "ft_split.json")

# Lĩnh vực theo luật gốc -> để phân tầng split
DOMAIN = {
    "15/2023/QH15": "KCB",
    "105/2016/QH13": "Duoc", "44/2024/QH15": "Duoc", "39/VBHN-VPQH": "Duoc",
    "55/2010/QH12": "ATTP", "61/VBHN-VPQH": "ATTP", "02/VBHN-VPQH": "ATTP",
    "46/2014/QH13": "BHYT", "51/2024/QH15": "BHYT",
    "09/2012/QH13": "ThuocLa", "08/VBHN-VPQH": "ThuocLa", "15/VBHN-VPQH": "ThuocLa",
    "11/VBHN-VPQH": "ThuocLa",
    "44/2019/QH14": "RuouBia",
    "75/2006/QH11": "HienTang",
    "64/2006/QH11": "HIV", "33/VBHN-VPQH": "HIV",
    "114/2025/QH15": "PhongBenh",
}


def domain_of(q):
    for dn in q["relevant"]:
        if dn in DOMAIN:
            return DOMAIN[dn]
    return "Khac"


def make_split():
    nat = [(i, q) for i, q in enumerate(golden) if q.get("type") == "natural"]
    by_dom = {}
    for i, q in nat:
        by_dom.setdefault(domain_of(q), []).append(i)
    train, test = [], []
    for dom in sorted(by_dom):
        ids = sorted(by_dom[dom])               # deterministic
        n_test = max(1, round(len(ids) * 0.3))  # ~30% test mỗi lĩnh vực
        # lấy test rải đều: các vị trí cách đều thay vì cụm cuối
        step = len(ids) / n_test
        test_pos = {int(k * step) for k in range(n_test)}
        for pos, i in enumerate(ids):
            (test if pos in test_pos else train).append(i)
    train.sort(); test.sort()
    json.dump({"train": train, "test": test,
               "by_domain": {d: sorted(v) for d, v in by_dom.items()}},
              open(SPLIT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Split: {len(train)} train / {len(test)} test (lĩnh vực: "
          + ", ".join(f"{d}:{len(v)}" for d, v in sorted(by_dom.items())) + ")")
    return train, test


def main():
    train_ids, test_ids = make_split()
    print("Nạp model gốc + Chroma để mining positive...", flush=True)
    model = SentenceTransformer(EMBED_MODEL, device="cpu")
    coll = chromadb.PersistentClient(path=CHROMA_DIR).get_collection(COLLECTION)

    examples = []
    for i in train_ids:
        q = golden[i]["q"]; rels = golden[i]["relevant"]
        seg_q = ViTokenizer.tokenize(q)
        emb = model.encode([seg_q], normalize_embeddings=True).tolist()
        # vector-search GIỚI HẠN trong các luật đúng -> chunk liên quan nhất (hard positive)
        res = coll.query(query_embeddings=emb, n_results=3,
                         where={"document_number": {"$in": rels}},
                         include=["documents"])
        docs = res["documents"][0] if res["documents"] else []
        for d in docs[:3]:
            if d and len(d.strip()) > 20:
                examples.append(InputExample(texts=[seg_q, ViTokenizer.tokenize(d)]))
    print(f"Số cặp huấn luyện: {len(examples)} (từ {len(train_ids)} câu train)", flush=True)

    loader = DataLoader(examples, shuffle=True, batch_size=16)
    loss = losses.MultipleNegativesRankingLoss(model)
    steps = len(loader)
    print(f"Bắt đầu fine-tune: 2 epoch, {steps} step/epoch (CPU)...", flush=True)
    model.fit(train_objectives=[(loader, loss)], epochs=2,
              warmup_steps=max(1, steps // 10), show_progress_bar=True,
              output_path=OUT_MODEL)
    print(f"✅ Đã lưu model fine-tune -> {OUT_MODEL}", flush=True)


if __name__ == "__main__":
    main()
