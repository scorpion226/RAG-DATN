# -*- coding: utf-8 -*-
"""Các kỹ thuật mở rộng/chuẩn hóa truy vấn deterministic (không cần LLM):
  #1 mined_expand  — nối thuật ngữ pháp lý khai thác từ "Giải thích từ ngữ" (mined_terms.json)
  #2 rm3_expand    — pseudo-relevance feedback: lấy từ khóa từ top-k đoạn truy xuất rồi nối lại
  #3 normalize_query — mở rộng viết tắt + chuẩn hóa
Dùng kèm từ điển ánh xạ (query_expand.expand_query)."""
import os, re, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- Mở rộng NGỮ NGHĨA bằng lexicon pháp lý lớn (TN12) ----------
_LEX = None


def load_lexicon():
    """Nạp lexicon cụm pháp lý + embedding bge-m3 (train/lexicon*.npy)."""
    global _LEX
    if _LEX is None:
        import numpy as np
        lp = os.path.join(HERE, "train", "lexicon.json")
        ep = os.path.join(HERE, "train", "lexicon_emb.npy")
        if os.path.exists(lp) and os.path.exists(ep):
            _LEX = (json.load(open(lp, encoding="utf-8")), np.load(ep).astype("float32"))
        else:
            _LEX = ([], None)
    return _LEX


def semantic_terms(query_vec, K=3, tau=0.45):
    """Trả về top-K cụm pháp lý GẦN nhất trong lexicon (cosine ≥ tau). query_vec đã chuẩn hóa."""
    import numpy as np
    lex, emb = load_lexicon()
    if emb is None or not lex:
        return []
    sims = emb @ np.asarray(query_vec, dtype="float32")
    out = []
    for j in np.argsort(-sims)[:K]:
        if sims[j] >= tau:
            out.append(lex[j])
    return out

# ---------- #3 Chuẩn hóa: mở rộng viết tắt thông dụng ----------
ACRONYMS = {
    "bhyt": "bảo hiểm y tế", "attp": "an toàn thực phẩm", "kcb": "khám bệnh chữa bệnh",
    "vbqppl": "văn bản quy phạm pháp luật", "tncn": "tác hại của thuốc lá",
    "hiv": "HIV", "aids": "AIDS", "ubnd": "ủy ban nhân dân", "byt": "bộ y tế",
    "vsattp": "vệ sinh an toàn thực phẩm", "bvtv": "bảo vệ thực vật",
}


def normalize_query(q):
    out = q
    for ab, full in ACRONYMS.items():
        out = re.sub(r"\b" + re.escape(ab) + r"\b", full, out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out).strip()
    return out


# ---------- #1 Mở rộng bằng thuật ngữ khai thác từ glossary ----------
_MINED = None


def _load_mined():
    global _MINED
    if _MINED is None:
        path = os.path.join(HERE, "eval", "mined_terms.json")
        _MINED = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    return _MINED


def mined_expand(q, max_terms=3, min_cue=2):
    """Nếu câu hỏi chứa >= min_cue từ khóa mô tả của một thuật ngữ -> nối thuật ngữ đó."""
    ql = q.lower()
    added = []
    for e in _load_mined():
        if e["term"] in ql:
            continue  # đã có sẵn
        hit = sum(1 for c in e["cues"] if c in ql)
        if hit >= min_cue:
            added.append(e["term"])
        if len(added) >= max_terms:
            break
    return q + (" " + " ".join(added) if added else "")


# ---------- #2 RM3 pseudo-relevance feedback ----------
STOP = set("là và của các một trong được người khi cho về theo hoặc đối với những tại "
           "có thể mà thì này đó nhằm cũng đã sẽ bị do từ nếu để trên dưới sau trước "
           "với không như còn ra vào lên xuống tới đến quy định pháp luật điều khoản".split())


def rm3_expand(q, feedback_texts, n_terms=6):
    """Trích n_terms từ khóa nổi bật nhất trong các đoạn phản hồi (top-k) rồi nối vào q.
    feedback_texts: list văn bản của top-k đoạn truy xuất ở vòng 1."""
    cnt = collections.Counter()
    qwords = set(re.findall(r"[a-zà-ỹđ]{3,}", q.lower()))
    for t in feedback_texts:
        for w in re.findall(r"[a-zà-ỹđ]{4,}", (t or "").lower()):
            if w in STOP or w in qwords:
                continue
            cnt[w] += 1
    top = [w for w, _ in cnt.most_common(n_terms)]
    return q + (" " + " ".join(top) if top else "")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(normalize_query("Sinh viên có bắt buộc mua BHYT không?"))
    print(mined_expand("Tôi muốn hiến mô bộ phận cơ thể thì làm sao?"))
