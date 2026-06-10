"""Vẽ lược đồ tuần tự (sequence diagram) xử lý một câu hỏi."""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
os.makedirs(OUT, exist_ok=True)
plt.rcParams["font.family"] = "DejaVu Sans"

actors = ["Người dùng", "Web/FastAPI", "Retriever", "ChromaDB +\nBM25", "Reranker\n(PhoRanker)", "PhoGPT"]
x = {a: i for i, a in enumerate(actors)}
fig, ax = plt.subplots(figsize=(11, 7.2)); ax.axis("off")
ax.set_xlim(-0.5, len(actors) - 0.5); ax.set_ylim(0, 12)

# lifelines + đầu cột
for a, i in x.items():
    ax.add_patch(Rectangle((i - 0.42, 11.1), 0.84, 0.7, fc="#1761d2", ec="#0d3a8a"))
    ax.text(i, 11.45, a, ha="center", va="center", color="white", fontsize=9, weight="bold")
    ax.plot([i, i], [0.3, 11.1], color="#9aa7bd", lw=1, ls="--")

msgs = [
    (0, 1, "Gửi câu hỏi (POST /chat)", 10.4),
    (1, 2, "tách từ + embedding", 9.6),
    (2, 3, "truy vấn top-N (vector + BM25)", 8.8),
    (3, 2, "các đoạn ứng viên", 8.0),
    (2, 2, "RRF + nhận diện số hiệu", 7.2),
    (2, 4, "xếp lại top-N ứng viên", 6.4),
    (4, 2, "top-k đoạn tốt nhất", 5.6),
    (2, 1, "ngữ cảnh + nguồn", 4.8),
    (1, 5, "prompt (ngữ cảnh + câu hỏi)", 4.0),
    (5, 1, "câu trả lời", 3.0),
    (1, 0, "câu trả lời + danh sách nguồn", 2.0),
]
for src, dst, label, y in msgs:
    if src == dst:  # self-call
        ax.add_patch(FancyArrowPatch((src + 0.05, y + 0.18), (src + 0.05, y - 0.18),
                     connectionstyle="arc3,rad=-2.2", arrowstyle="-|>", mutation_scale=12,
                     color="#0d9488", lw=1.4))
        ax.text(src + 0.5, y, label, ha="left", va="center", fontsize=8.2, color="#0d6b5a")
    else:
        col = "#33415c" if dst > src else "#a15a1c"
        ax.add_patch(FancyArrowPatch((src, y), (dst, y), arrowstyle="-|>", mutation_scale=14,
                     color=col, lw=1.5, ls="-" if dst > src else (0, (4, 2))))
        mid = (src + dst) / 2
        ax.text(mid, y + 0.12, label, ha="center", va="bottom", fontsize=8.2, color=col)

ax.set_title("Lược đồ tuần tự: xử lý một câu hỏi của người dùng", fontsize=12)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "sequence.png"), dpi=160, bbox_inches="tight")
print("Đã lưu figs/sequence.png")
