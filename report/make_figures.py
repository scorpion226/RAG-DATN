"""Sinh hình minh họa cho báo cáo: biểu đồ so sánh retrieval + sơ đồ kiến trúc."""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

OUT = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(OUT, "figs"), exist_ok=True)
plt.rcParams["font.family"] = "DejaVu Sans"  # hỗ trợ tiếng Việt

# ---------- Hình 1: So sánh các cấu hình retrieval ----------
configs = ["Không\ntách từ", "Vector\n+pyvi", "Vector\n+Rerank", "Hybrid", "Hybrid\n+Rerank"]
metrics = {
    "Hit@1":  [0.490, 0.595, 0.625, 0.635, 0.650],
    "Hit@5":  [0.760, 0.845, 0.850, 0.900, 0.905],
    "Hit@10": [0.810, 0.885, 0.880, 0.960, 0.940],
    "MRR":    [0.600, 0.704, 0.724, 0.754, 0.764],
}
x = np.arange(len(configs)); w = 0.2
fig, ax = plt.subplots(figsize=(9, 4.8))
colors = ["#9bb7e0", "#1761d2", "#0d9488", "#f59e0b"]
for i, (name, vals) in enumerate(metrics.items()):
    ax.bar(x + (i - 1.5) * w, vals, w, label=name, color=colors[i])
ax.set_xticks(x); ax.set_xticklabels(configs, fontsize=9)
ax.set_ylabel("Giá trị"); ax.set_ylim(0, 1.08)
ax.set_title("So sánh chất lượng truy xuất giữa các cấu hình (200 câu hỏi vàng)")
ax.legend(ncol=4, fontsize=9, loc="upper left")
ax.grid(axis="y", alpha=0.3)
for i, vals in enumerate(metrics.values()):
    for j, v in enumerate(vals):
        ax.text(x[j] + (i - 1.5) * w, v + 0.012, f"{v:.2f}", ha="center", fontsize=6.5)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "figs", "retrieval_comparison.png"), dpi=160)
print("Đã lưu figs/retrieval_comparison.png")

# ---------- Hình 2: Sơ đồ kiến trúc RAG ----------
fig, ax = plt.subplots(figsize=(7.2, 8.2)); ax.axis("off")
ax.set_xlim(0, 10); ax.set_ylim(0, 14)
def box(x, y, w, h, text, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                fc=fc, ec="#33415c", lw=1.3))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=9.5, wrap=True)
def arrow(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                mutation_scale=16, color="#33415c", lw=1.4))
box(3.2, 12.6, 3.6, 0.9, "Câu hỏi người dùng", "#e7effb")
arrow(5, 12.6, 5, 12.0)
box(2.6, 11.0, 4.8, 0.9, "Tách từ (pyvi) + Embedding\nPhoBERT bi-encoder (768d)", "#dfeaf7")
arrow(5, 11.0, 3.2, 10.3); arrow(5, 11.0, 6.8, 10.3)
box(0.6, 9.3, 3.6, 0.95, "Vector search\n(ChromaDB, cosine)", "#d6f3ea")
box(5.2, 9.3, 3.6, 0.95, "BM25\n(bm25s)", "#d6f3ea")
arrow(2.4, 9.3, 4.3, 8.6); arrow(7.0, 9.3, 5.7, 8.6)
box(2.8, 7.6, 4.4, 0.95, "RRF fusion +\nnhận diện số hiệu VB", "#fdeecb")
arrow(5, 7.6, 5, 7.0)
box(2.8, 6.0, 4.4, 0.9, "Reranker (PhoRanker\ncross-encoder) → top-k", "#fde2e2")
arrow(5, 6.0, 5, 5.4)
box(2.4, 4.4, 5.2, 0.9, "Prompt: ngữ cảnh + yêu cầu\ntrích dẫn, chống bịa", "#eee6fb")
arrow(5, 4.4, 5, 3.8)
box(2.8, 2.8, 4.4, 0.9, "PhoGPT-4B-Chat\n(GGUF Q4, llama.cpp)", "#e7effb")
arrow(5, 2.8, 5, 2.2)
box(2.2, 1.0, 5.6, 0.95, "Câu trả lời + nguồn trích dẫn\n(số hiệu, hiệu lực, đoạn)", "#dfeaf7")
ax.set_title("Kiến trúc hệ thống RAG", fontsize=12, y=0.99)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "figs", "architecture.png"), dpi=160)
print("Đã lưu figs/architecture.png")

# ---------- Hình 3: Quy mô dữ liệu (phễu) ----------
fig, ax = plt.subplots(figsize=(7.5, 3.6)); ax.axis("off")
stages = [("518.601 VB pháp luật (toàn bộ)", "#cdd9ee"),
          ("34.166 VB ngành Y tế có nội dung", "#a9c2e8"),
          ("21.490 VB còn hiệu lực", "#7aa0db"),
          ("367.462 chunk sạch (sau khử trùng lặp)", "#1761d2")]
for i, (t, c) in enumerate(stages):
    wfr = 1.0 - i * 0.16
    ax.add_patch(FancyBboxPatch(((1-wfr)*5, 3-i*0.8), wfr*10, 0.62,
                 boxstyle="round,pad=0.02", fc=c, ec="white"))
    ax.text(5, 3.3 - i*0.8, t, ha="center", va="center", fontsize=9.5,
            color="white" if i >= 2 else "#1a2433")
ax.set_xlim(0, 10); ax.set_ylim(-0.2, 4)
ax.set_title("Quy trình lọc dữ liệu", fontsize=11)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "figs", "data_funnel.png"), dpi=160)
print("Đã lưu figs/data_funnel.png")
print("XONG")
