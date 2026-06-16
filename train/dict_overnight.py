# -*- coding: utf-8 -*-
"""MỞ RỘNG TỪ ĐIỂN TỐI ĐA (chạy qua đêm, GPU). Hai hướng tự động, không cần API:
 (A) Lexicon pháp lý LỚN: trích sạch tiêu đề "Điều" + thuật ngữ glossary toàn corpus
     -> embed bge-m3 -> MỞ RỘNG NGỮ NGHĨA: với mỗi câu hỏi, nối top-K cụm pháp lý GẦN nhất.
 (B) So với từ điển tay (expand_query) + glossary cue (mined).
Grid-search trên TRAIN split (71 câu), báo cáo trên TEST (29) + FULL (100) để TRÁNH OVERFIT.
Truy xuất: bge-m3 vector mở (collection bge_m3). Đo strict + topic-level.
Chạy: python train/dict_overnight.py
"""
import sys, os, re, json, time
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
LEX_NPY = os.path.join(HERE, "lexicon_emb.npy")
LEX_TXT = os.path.join(HERE, "lexicon.json")

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
JUNK = ["này;", "này được", "b)", "c)", "Thông tư", "Nghị định này", "Khoản", "Điều ", ";"]
STOP_TITLE = ["phạm vi điều chỉnh", "đối tượng áp dụng", "giải thích từ ngữ", "hiệu lực thi hành",
              "tổ chức thực hiện", "điều khoản thi hành", "trách nhiệm thi hành", "quy định chuyển tiếp"]


def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def build_lexicon():
    titles = set()
    pf = pq.ParquetFile(os.path.join(ROOT, "legal_medical_chunks_clean.parquet"))
    for b in pf.iter_batches(columns=["text"], batch_size=10000):
        for t in b.to_pydict()["text"]:
            for m in TITLE_RE.findall(t):
                ti = re.split(r"\d", m)[0].strip().rstrip(".,;:").strip()
                low = ti.lower()
                if not (8 <= len(ti) <= 80) or ti.isupper():
                    continue
                if any(j in ti for j in JUNK) or any(s in low for s in STOP_TITLE):
                    continue
                if low.split()[0] in ("thông", "nghị", "khoản", "căn", "trường"):
                    continue
                titles.add(ti)
    lex = sorted(titles)
    json.dump(lex, open(LEX_TXT, "w", encoding="utf-8"), ensure_ascii=False)
    log(f"Lexicon sạch: {len(lex)} cụm pháp lý")
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

    # ---- lexicon + embed (cache) ----
    if os.path.exists(LEX_NPY) and os.path.exists(LEX_TXT):
        lex = json.load(open(LEX_TXT, encoding="utf-8")); lex_emb = np.load(LEX_NPY)
        log(f"Nạp lexicon cache: {len(lex)}")
    else:
        lex = build_lexicon()
        log("Embed lexicon bằng bge-m3...")
        lex_emb = bge.encode(lex, batch_size=128, normalize_embeddings=True, show_progress_bar=False)
        lex_emb = np.asarray(lex_emb, dtype=np.float32); np.save(LEX_NPY, lex_emb)
        log("Đã embed + lưu lexicon_emb.npy")

    # topic-level family
    import pickle
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

    # cache query embeddings (raw) cho semantic expansion
    qtext = {i: golden[i]["q"] for i in NAT}
    qemb_raw = {i: bge.encode([qtext[i]], normalize_embeddings=True)[0] for i in NAT}

    def semantic_terms(i, K, tau):
        sims = lex_emb @ qemb_raw[i]
        idx = np.argsort(-sims)[:K]
        return [lex[j] for j in idx if sims[j] >= tau]

    def retrieve(query):
        emb = bge.encode([query], normalize_embeddings=True).tolist()
        r = coll.query(query_embeddings=emb, n_results=15, where=WHERE, include=["metadatas"])
        seen = []
        for m in r["metadatas"][0]:
            dn = m.get("document_number")
            if dn and dn not in seen: seen.append(dn)
        return seen

    # ---- build các cấu hình truy vấn ----
    def q_base(i): return qtext[i]
    def q_manual(i): return expand_query(qtext[i])
    def make_sem(K, tau, with_manual):
        def f(i):
            base = expand_query(qtext[i]) if with_manual else qtext[i]
            terms = semantic_terms(i, K, tau)
            return base + (" " + " ".join(terms) if terms else "")
        return f

    configs = {"base": q_base, "manual": q_manual}
    for K in (1, 2, 3):
        for tau in (0.45, 0.55, 0.65):
            configs[f"sem_K{K}_t{tau}"] = make_sem(K, tau, False)
            configs[f"man+sem_K{K}_t{tau}"] = make_sem(K, tau, True)

    results = {}
    for name, fn in configs.items():
        docs_all = {i: retrieve(fn(i)) for i in NAT}
        tr = [(docs_all[i], rs(i)) for i in NAT if i in TRAIN]
        te = [(docs_all[i], rs(i)) for i in NAT if i in TEST]
        full_s = [(docs_all[i], rs(i)) for i in NAT]
        full_t = [(docs_all[i], rt(i)) for i in NAT]
        results[name] = {"train_strict": metrics(tr), "test_strict": metrics(te),
                         "full_strict": metrics(full_s), "full_topic": metrics(full_t)}
        log(f"{name:18} train Hit@1={results[name]['train_strict']['Hit@1']} "
            f"test Hit@1={results[name]['test_strict']['Hit@1']} "
            f"full Hit@1={results[name]['full_strict']['Hit@1']} "
            f"full topic Hit@10={results[name]['full_topic']['Hit@10']}")
        json.dump(results, open(os.path.join(HERE, "dict_overnight.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    # chọn cấu hình tốt nhất theo TRAIN (strict MRR), báo cáo test + full
    best = max(results, key=lambda c: results[c]["train_strict"]["MRR"])
    log(f"==> BEST theo train MRR: {best}")
    log(f"    test:  {results[best]['test_strict']}")
    log(f"    full strict: {results[best]['full_strict']} | full topic: {results[best]['full_topic']}")
    json.dump({"best_by_train": best, "all": results},
              open(os.path.join(HERE, "dict_overnight.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    log("✅ Lưu train/dict_overnight.json")


if __name__ == "__main__":
    main()
