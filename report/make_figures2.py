"""Sinh thêm hình cho báo cáo tuần: ảnh mẫu dữ liệu (bảng) + biểu đồ loại văn bản."""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
os.makedirs(OUT, exist_ok=True)
plt.rcParams["font.family"] = "DejaVu Sans"

# ---- Hình: mẫu dữ liệu sau khi chunk ----
cols = ["chunk_id", "Số hiệu", "Loại", "Hiệu lực", "Trích đoạn (rút gọn)"]
data = [
    ["695018_0", "08/2026/QĐ-UBND", "Decision", "In effect", "ỦY BAN NHÂN DÂN THÀNH PHỐ HỒ CHÍ MINH; CỘNG HÒA…"],
    ["695018_1", "08/2026/QĐ-UBND", "Decision", "In effect", "…ban hành Quy định về quy trình xây dựng văn bản…"],
    ["695018_2", "08/2026/QĐ-UBND", "Decision", "In effect", "…b) Ủy ban nhân dân xã, phường, đặc khu; c) Các…"],
    ["695018_3", "08/2026/QĐ-UBND", "Decision", "In effect", "…chất gây nghiện, dược chất hướng thần, tiền chất…"],
]
fig, ax = plt.subplots(figsize=(11, 2.2)); ax.axis("off")
tb = ax.table(cellText=data, colLabels=cols, loc="center",
              cellLoc="left", colColours=["#1761d2"]*5)
tb.auto_set_font_size(False); tb.set_fontsize(8.5); tb.scale(1, 1.6)
for (r, c), cell in tb.get_celld().items():
    cell.set_edgecolor("#b8c4d6")
    if r == 0:
        cell.set_text_props(color="white", weight="bold")
colw = [0.10, 0.16, 0.10, 0.10, 0.54]
for (r, c), cell in tb.get_celld().items():
    cell.set_width(colw[c])
ax.set_title("Mẫu dữ liệu sau khi lọc, làm sạch và phân đoạn (chunk)", fontsize=11, pad=8)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "sample_data.png"), dpi=160, bbox_inches="tight")
print("Đã lưu figs/sample_data.png")

# ---- Hình: phân bố loại văn bản ----
labels = ["Quyết định", "Công văn", "Nghị quyết", "Chỉ thị", "Thông tư", "Công điện", "Khác"]
vals = [10343, 8399, 752, 654, 510, 243, 600]
fig, ax = plt.subplots(figsize=(8, 4))
bars = ax.bar(labels, vals, color="#1761d2")
ax.bar_label(bars, fmt="%d", fontsize=9)
ax.set_ylabel("Số văn bản"); ax.set_title("Phân bố loại văn bản trong corpus (21.490 văn bản)")
ax.set_ylim(0, 11500)
plt.xticks(rotation=18, fontsize=9); ax.grid(axis="y", alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "doctype_dist.png"), dpi=160)
print("Đã lưu figs/doctype_dist.png")
print("XONG")
