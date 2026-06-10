"""Biểu đồ Precision/Recall/F1 theo k + thời gian phản hồi (từ experiment_results.json)."""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figs"); os.makedirs(OUT, exist_ok=True)
plt.rcParams["font.family"] = "DejaVu Sans"
d = json.load(open(os.path.join(os.path.dirname(HERE), "eval", "experiment_results.json"), encoding="utf-8"))

pr = d["precision_recall"]
ks = [int(k) for k in pr]
P = [pr[str(k)]["P"] for k in ks]; R = [pr[str(k)]["R"] for k in ks]; F = [pr[str(k)]["F1"] for k in ks]

# --- P/R/F1 theo k ---
fig, ax = plt.subplots(figsize=(7.5, 4.5))
ax.plot(ks, P, "o-", label="Precision", color="#1761d2", lw=2)
ax.plot(ks, R, "s-", label="Recall", color="#0d9488", lw=2)
ax.plot(ks, F, "^--", label="F1", color="#f59e0b", lw=2)
for xs, ys in [(ks, P), (ks, R), (ks, F)]:
    for x, y in zip(xs, ys): ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 6), fontsize=8, ha="center")
ax.set_xlabel("Số nguồn k"); ax.set_ylabel("Giá trị"); ax.set_xticks(ks); ax.set_ylim(0, 0.8)
ax.set_title("Precision / Recall / F1 theo số nguồn k (Hybrid + Reranker)")
ax.legend(); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "precision_recall_k.png"), dpi=160)
print("Đã lưu figs/precision_recall_k.png")

# --- Thời gian phản hồi ---
fig, ax = plt.subplots(figsize=(5.2, 4))
bars = ax.bar(["Truy xuất", "Sinh (PhoGPT)"], [d["avg_retrieval_s"], d["avg_gen_s"]],
              color=["#0d9488", "#f59e0b"])
ax.bar_label(bars, fmt="%.1f s", fontsize=11)
ax.set_ylabel("Thời gian trung bình (giây)")
ax.set_title("Thời gian phản hồi trung bình (CPU)")
ax.set_ylim(0, max(d["avg_gen_s"], d["avg_retrieval_s"]) * 1.25)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "latency.png"), dpi=160)
print("Đã lưu figs/latency.png")
print("XONG")
