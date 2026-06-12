"""Biểu đồ P/R/F1 + trần Precision theo k=1..10 (từ eval/pr_sweep.json)."""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figs"); os.makedirs(OUT, exist_ok=True)
plt.rcParams["font.family"] = "DejaVu Sans"
d = json.load(open(os.path.join(os.path.dirname(HERE), "eval", "eval200.json"), encoding="utf-8"))["sweep"]
ks = [int(k) for k in d]
P = [d[str(k)]["P"] for k in ks]; R = [d[str(k)]["R"] for k in ks]
F = [d[str(k)]["F1"] for k in ks]; C = [d[str(k)]["ceilP"] for k in ks]

fig, ax = plt.subplots(figsize=(8.5, 5))
ax.plot(ks, P, "o-", label="Precision", color="#1761d2", lw=2)
ax.plot(ks, R, "s-", label="Recall", color="#0d9488", lw=2)
ax.plot(ks, F, "^-", label="F1", color="#f59e0b", lw=2.4)
ax.plot(ks, C, "--", label="Trần Precision", color="#9aa7bd", lw=1.6)
# đánh dấu F1 cực đại
fmax = max(range(len(F)), key=lambda i: F[i])
ax.scatter([ks[fmax]], [F[fmax]], s=120, facecolors="none", edgecolors="#d97706", lw=2, zorder=5)
ax.annotate(f"F1 cực đại (k={ks[fmax]}: {F[fmax]:.3f})", (ks[fmax], F[fmax]),
            textcoords="offset points", xytext=(10, 14), fontsize=9, color="#a15a1c")
ax.set_xlabel("Số nguồn k"); ax.set_ylabel("Giá trị"); ax.set_xticks(ks); ax.set_ylim(0, 1.05)
ax.set_title("Precision / Recall / F1 theo số nguồn k (200 câu, Hybrid + Reranker)")
ax.legend(loc="center right"); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "pr_sweep.png"), dpi=160)
print("Đã lưu figs/pr_sweep.png")
