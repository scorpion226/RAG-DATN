# -*- coding: utf-8 -*-
"""MỞ RỘNG NGỮ NGHĨA v2: lexicon LỚN HƠN = tiêu đề Điều + CHỦ ĐỀ văn bản (sạch) + thuật ngữ
glossary. Embed bge-m3, grid tập trung (man+sem, K∈{3,4,5}, τ∈{0.40,0.45,0.50}) so với v1 (0.36).
Train/test split (71/29) tránh overfit. Chạy: python train/dict_overnight_v2.py"""
import sys, os, re, json, time, pickle
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer
import chromadb, torch
from query_expand import expand_query

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
golden = json.load(open(os.path.join(ROOT, "eval", "golden_questions.json"), encoding="utf-8"))
split = json.load(open(os.path.join(HERE, "ft_split.json"), encoding="utf-8"))
TRAIN, TEST = set(split["train"]), set(split["test"])
NAT = [i for i, q in enumerate(golden) if q.get("type") == "natural"]
WHERE = {"effect_status": "In effect"}; KS = [1, 3, 5, 10]
DEV = "cuda" if torch.cuda.is_available() else "cpu"
LEX_TXT = os.path.join(HERE, "lexicon_v2.json"); LEX_NPY = os.path.join(HERE, "lexicon_v2_emb.npy")

LAWNAME = {"15/2023/QH15": "luật khám bệnh, chữa bệnh", "105/2016/QH13": "luật dược",
           "44/2024/QH15": "luật dược", "39/VBHN-VPQH": "luật dược",
           "55/2010/QH12": "luật an toàn thực phẩm", "61/VBHN-VPQH": "luật an toàn thực phẩm",
           "02/VBHN-VPQH": "luật an toàn thực phẩm", "46/2014/QH13": "luật bảo hiểm y tế",
           "51/2024/QH15": "luật bảo hiểm y tế", "09/2012/QH13": "phòng, chống tác hại của thuốc lá",
           "08/VBHN-VPQH": "phòng, chống tác hại của thuốc lá", "15/VBHN-VPQH": "phòng, chống tác hại của thuốc lá",
           "11/VBHN-VPQH": "phòng, chống tác hại của thuốc lá", "44/2019/QH14": "phòng, chống tác hại của rượu, bia",
           "75/2006/QH11": "hiến, lấy, ghép mô", "64/2006/QH11": "phòng, chống nhiễm vi rút gây ra hội chứng",
           "33/VBHN-VPQH": "phòng, chống nhiễm vi rút gây ra hội chứng", "114/2025/QH15": "luật phòng bệnh"}
MARK = ["hướng dẫn", "hợp nhất", "quy định chi tiết", "biện pháp thi hành", "quy định và biện pháp"]
TITLE_RE = re.compile(r"Điều\s+\d+[\.:]?\s+([A-ZÀ-ỸĐ][^\n]{6,90})")
SUBJ_RE = re.compile(r"(?:về|hướng dẫn|quy định về|quy định)\s+(.{8,90})")
JUNK = ["này;", "này được", "b)", "c)", "Thông tư", "Nghị định này", "Khoản", ";"]
STOP_TITLE = ["phạm vi điều chỉnh", "đối tượng áp dụng", "giải thích từ ngữ", "hiệu lực thi hành",
              "tổ chức thực hiện", "điều khoản thi hành", "trách nhiệm thi hành", "quy định chuyển tiếp"]


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def clean_subj(s):
    s = re.split(r"\s+do\s+|\s+ngày\s+|\s+giai đoạn\s+|\s+năm \d{4}", s)[0]
    return s.strip().rstrip(".,;:").strip()


def build_lexicon():
    titles, subjects = set(), set()
    pf = pq.ParquetFile(os.path.join(ROOT, "legal_medical_chunks_clean.parquet"))
    seen_titles = set()
    for b in pf.iter_batches(columns=["text", "title"], batch_size=10000):
        d = b.to_pydict()
        for t, ti in zip(d["text"], d["title"]):
            for m in TITLE_RE.findall(t):
                x = re.split(r"\d", m)[0].strip().rstrip(".,;:").strip(); low = x.lower()
                if 8 <= len(x) <= 80 and not x.isupper() and not any(j in x for j in JUNK) \
                        and not any(s in low for s in STOP_TITLE) and low.split()[0] not in ("thông", "nghị", "khoản", "căn", "trường"):
                    titles.add(x)
            if ti and ti not in seen_titles:
                seen_titles.add(ti)
                mm = SUBJ_RE.search(ti)
                if mm:
                    s = clean_subj(mm.group(1))
                    if 10 <= len(s) <= 80 and not any(j in s for j in JUNK):
                        subjects.add(s)
    # glossary terms
    gloss = set()
    gp = os.path.join(HERE, "..", "eval", "mined_terms.json")
    if os.path.exists(gp):
        for e in json.load(open(gp, encoding="utf-8")):
            if 6 <= len(e["term"]) <= 70: gloss.add(e["term"])
    lex = sorted(titles | subjects | gloss)
    log(f"Lexicon v2: {len(lex)} cụm (Điều {len(titles)} + chủ đề VB {len(subjects)} + glossary {len(gloss)})")
    json.dump(lex, open(LEX_TXT, "w", encoding="utf-8"), ensure_ascii=False)
    return lex


def metrics(items):
    hit = {k: 0 for k in KS}; rr = 0.0; n = len(items)
    for docs, rel in items:
        first = next((i + 1 for i, dn in enumerate(docs) if dn in rel), None)
        rr += (1.0 / first) if first else 0.0
        for k in KS:
            if any(dn in rel for dn in docs[:k]): hit[k] += 1
    return {**{f"Hit@{k}": round(hit[k] / n, 3) for k in KS}, "MRR": round(rr / n, 3), "n": n}


def main():
    log(f"device={DEV}")
    bge = SentenceTransformer("BAAI/bge-m3", device=DEV)
    if DEV == "cuda": bge.half()
    bge.max_seq_length = 256
    coll = chromadb.PersistentClient(path=os.path.join(ROOT, "chroma_db")).get_collection("bge_m3")

    if os.path.exists(LEX_NPY) and os.path.exists(LEX_TXT):
        lex = json.load(open(LEX_TXT, encoding="utf-8")); lex_emb = np.load(LEX_NPY)
        log(f"Nạp lexicon v2 cache: {len(lex)}")
    else:
        lex = build_lexicon()
        log("Embed lexicon v2...")
        lex_emb = np.asarray(bge.encode(lex, batch_size=128, normalize_embeddings=True,
                                        show_progress_bar=False), dtype=np.float32)
        np.save(LEX_NPY, lex_emb); log("Đã lưu lexicon_v2_emb.npy")

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

    qtext = {i: golden[i]["q"] for i in NAT}
    qemb_raw = {i: bge.encode([qtext[i]], normalize_embeddings=True)[0] for i in NAT}

    def sem_terms(i, K, tau):
        sims = lex_emb @ np.asarray(qemb_raw[i], dtype=np.float32)
        return [lex[j] for j in np.argsort(-sims)[:K] if sims[j] >= tau]

    def retrieve(query):
        emb = bge.encode([query], normalize_embeddings=True).tolist()
        r = coll.query(query_embeddings=emb, n_results=15, where=WHERE, include=["metadatas"])
        seen = []
        for m in r["metadatas"][0]:
            dn = m.get("document_number")
            if dn and dn not in seen: seen.append(dn)
        return seen

    def make(K, tau):
        def f(i):
            terms = sem_terms(i, K, tau)
            return expand_query(qtext[i]) + (" " + " ".join(terms) if terms else "")
        return f

    configs = {"manual": lambda i: expand_query(qtext[i])}
    for K in (3, 4, 5):
        for tau in (0.40, 0.45, 0.50):
            configs[f"man+sem_K{K}_t{tau}"] = make(K, tau)

    results = {}
    for name, fn in configs.items():
        da = {i: retrieve(fn(i)) for i in NAT}
        results[name] = {
            "train_strict": metrics([(da[i], rs(i)) for i in NAT if i in TRAIN]),
            "test_strict": metrics([(da[i], rs(i)) for i in NAT if i in TEST]),
            "full_strict": metrics([(da[i], rs(i)) for i in NAT]),
            "full_topic": metrics([(da[i], rt(i)) for i in NAT])}
        r = results[name]
        log(f"{name:18} train={r['train_strict']['Hit@1']} test={r['test_strict']['Hit@1']} "
            f"full={r['full_strict']['Hit@1']} topicH10={r['full_topic']['Hit@10']}")
        json.dump(results, open(os.path.join(HERE, "dict_overnight_v2.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    best = max(results, key=lambda c: results[c]["train_strict"]["MRR"])
    log(f"==> BEST theo train: {best} | test {results[best]['test_strict']} | "
        f"full {results[best]['full_strict']} | topic {results[best]['full_topic']}")
    json.dump({"best_by_train": best, "all": results},
              open(os.path.join(HERE, "dict_overnight_v2.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    log("✅ Lưu dict_overnight_v2.json")


if __name__ == "__main__":
    main()
