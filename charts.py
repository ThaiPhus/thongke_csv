"""
charts.py
---------
Sinh các biểu đồ trực quan hoá bằng matplotlib, trả về chuỗi PNG
dạng base64 (data URI) để có thể:
    - hiển thị trực tiếp trong Streamlit (nhúng trong thẻ .chart-card)
    - nhúng thẳng vào file báo cáo HTML (không cần lưu file ảnh riêng)

Bảng màu đồng bộ với theme Cobalt (xem tokens.css) — dùng chung một họ
màu xanh lạnh/tím cho toàn bộ dashboard thay vì màu rời rạc mỗi biểu đồ.
"""

from __future__ import annotations

import base64
import io
from typing import Sequence

import matplotlib
matplotlib.use("Agg")  # backend không cần màn hình, phù hợp môi trường server
import matplotlib.pyplot as plt

# ---- Bảng màu Cobalt (xấp xỉ hex của các token oklch trong tokens.css) ----
ACCENT = "#3457D5"
ACCENT_STRONG = "#22348C"
ACCENT_SOFT = "#DCE6FB"
INK = "#232B3D"
INK_SOFT = "#6B7690"
GRID = "#E6E9F2"

# Bảng màu định tính (nhiều nhóm) — cùng họ xanh lạnh/tím, tránh màu chỏi nhau
QUALITATIVE_PALETTE = ["#3457D5", "#00A6A6", "#6C63FF", "#2EC4B6", "#5C7AEA", "#94A3B8"]

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK_SOFT,
    "axes.titlecolor": INK,
    "axes.titleweight": "bold",
    "axes.titlesize": 12,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": INK_SOFT,
    "ytick.color": INK_SOFT,
    "font.size": 10,
    "text.color": INK,
})


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def _clean_axes(ax) -> None:
    """Bỏ viền trên/phải, chỉ giữ gridline ngang nhẹ — phong cách dashboard tối giản."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", visible=False)
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def bar_chart_by_group(labels: Sequence[str], values: Sequence[float], title: str, ylabel: str) -> str:
    fig, ax = plt.subplots(figsize=(7, 4.2))
    colors = [QUALITATIVE_PALETTE[i % len(QUALITATIVE_PALETTE)] for i in range(len(labels))]
    bars = ax.bar(labels, values, color=colors, width=0.6, zorder=3)
    ax.set_title(title, pad=12)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=25)
    _clean_axes(ax)
    for b in bars:
        h = b.get_height()
        ax.annotate(f"{h:,.0f}", (b.get_x() + b.get_width() / 2, h),
                    ha="center", va="bottom", fontsize=8.5, color=INK, fontweight="medium")
    fig.tight_layout()
    return _fig_to_base64(fig)


def histogram_chart(edges: Sequence[float], counts: Sequence[int], title: str, xlabel: str, focus_percentile: float = 99.0) -> str:
    """
    Vẽ histogram, tự động THU GỌN trục X quanh vùng chứa phần lớn dữ liệu
    (mặc định 99%) để tránh bị các giá trị ngoại lai (outlier) kéo dài trục,
    làm phần dữ liệu chính bị dồn nhỏ xíu sang một bên. Toàn bộ dữ liệu vẫn
    được TÍNH ĐẦY ĐỦ trong các cột (không cắt bỏ), chỉ thu hẹp VÙNG HIỂN THỊ.
    """
    edges = list(edges)
    counts = list(counts)
    total = sum(counts)

    # TRƯỜNG HỢP ĐẶC BIỆT: toàn bộ giá trị giống hệt nhau (min == max) khiến
    # mọi bin có bề rộng = 0 -> biểu đồ trống trơn dù dữ liệu có nhiều bản ghi.
    # Xử lý riêng: vẽ một cột duy nhất ở giữa kèm chú thích rõ ràng.
    if edges[0] == edges[-1]:
        fig, ax = plt.subplots(figsize=(7, 4.2))
        single_value = edges[0]
        ax.bar([0], [total], width=0.5, color=ACCENT_STRONG, zorder=3)
        ax.set_title(title, pad=12)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Số lượng bản ghi")
        ax.set_xticks([0])
        ax.set_xticklabels([f"{single_value:,.2f}"])
        ax.set_xlim(-1, 1)
        _clean_axes(ax)
        ax.text(
            0, total, f"Toàn bộ {total:,} bản ghi đều có cùng giá trị {single_value:,.2f}",
            ha="center", va="bottom", fontsize=9, color=INK,
        )
        fig.tight_layout()
        return _fig_to_base64(fig)

    xlim_max = edges[-1]
    clipped = False
    if total > 0:
        threshold = total * (focus_percentile / 100.0)
        cum = 0
        for i, c in enumerate(counts):
            cum += c
            if cum >= threshold:
                xlim_max = edges[i + 1]
                break
        clipped = xlim_max < edges[-1] * 0.999

    fig, ax = plt.subplots(figsize=(7, 4.2))
    widths = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
    # Tô đậm cột cao nhất (mode) bằng accent-strong, còn lại dùng accent nhạt hơn
    peak_idx = counts.index(max(counts)) if counts else -1
    bar_colors = [ACCENT_STRONG if i == peak_idx else ACCENT for i in range(len(counts))]
    ax.bar(edges[:-1], counts, width=widths, align="edge", color=bar_colors, edgecolor="white", linewidth=0.6, zorder=3)
    ax.set_title(title, pad=12)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Số lượng bản ghi")
    _clean_axes(ax)

    if clipped:
        ax.set_xlim(edges[0], xlim_max)
        ax.text(
            0.99, 0.97,
            f"* Trục X thu gọn quanh {focus_percentile:.0f}% dữ liệu\n  (đã lược bớt vài giá trị ngoại lai)",
            transform=ax.transAxes, ha="right", va="top", fontsize=8, color=INK_SOFT,
            bbox=dict(boxstyle="round", fc="white", ec=GRID, alpha=0.95),
        )

    fig.tight_layout()
    return _fig_to_base64(fig)


def line_chart_trend(x_labels: Sequence[str], values: Sequence[float], title: str, ylabel: str) -> str:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    x_pos = range(len(x_labels))
    ax.plot(x_pos, values, color=ACCENT, marker="o", markersize=3.5, linewidth=2, zorder=3)
    ax.fill_between(x_pos, values, color=ACCENT, alpha=0.08, zorder=2)
    ax.set_title(title, pad=12)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=45)
    _clean_axes(ax)
    # Chỉ hiện tối đa ~15 nhãn trục X để không bị rối khi có nhiều ngày
    step = max(1, len(x_labels) // 15)
    ax.set_xticks(list(x_pos)[::step])
    ax.set_xticklabels([x_labels[i] for i in range(0, len(x_labels), step)])
    fig.tight_layout()
    return _fig_to_base64(fig)


def pie_chart(labels: Sequence[str], values: Sequence[float], title: str, top_n: int = 6, min_label_pct: float = 3.0) -> str:
    """
    Vẽ biểu đồ DONUT (vành khuyên), GOM các nhóm nhỏ (ngoài top_n nhóm lớn
    nhất) vào một lát "Khác", chỉ hiện % trên lát đủ lớn (>= min_label_pct%)
    — tên nhóm đưa ra chú thích bên cạnh để tránh chồng chữ. Giữa vòng
    donut hiển thị tổng số bản ghi — điểm nhấn quen thuộc của dashboard.
    """
    pairs = sorted(zip(labels, values), key=lambda p: p[1], reverse=True)
    if len(pairs) > top_n:
        top = pairs[:top_n]
        rest_sum = sum(v for _, v in pairs[top_n:])
        if rest_sum > 0:
            top.append(("Khác", rest_sum))
        pairs = top

    plot_labels = [p[0] for p in pairs]
    plot_values = [p[1] for p in pairs]
    total = sum(plot_values)

    def _autopct(pct):
        return f"{pct:.1f}%" if pct >= min_label_pct else ""

    # "Khác" luôn dùng màu xám trung tính riêng (không lấy từ palette tuần
    # hoàn) để không bao giờ trùng màu với một nhóm thật ở phía trước.
    colors = []
    palette_i = 0
    for label in plot_labels:
        if label == "Khác":
            colors.append("#B8C0D0")
        else:
            colors.append(QUALITATIVE_PALETTE[palette_i % len(QUALITATIVE_PALETTE)])
            palette_i += 1

    fig, ax = plt.subplots(figsize=(7, 5))
    wedges, _texts, autotexts = ax.pie(
        plot_values,
        labels=None,
        autopct=_autopct,
        pctdistance=0.82,
        startangle=90,
        colors=colors,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=2),
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontsize(9)
        t.set_fontweight("medium")

    ax.text(0, 0.06, f"{total:,.0f}", ha="center", va="center", fontsize=16, fontweight="bold", color=INK)
    ax.text(0, -0.12, "tổng số", ha="center", va="center", fontsize=8.5, color=INK_SOFT)

    ax.legend(
        wedges, plot_labels, title="Nhóm",
        loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9, frameon=False,
    )
    ax.set_title(title, pad=12)
    ax.axis("equal")
    fig.tight_layout()
    return _fig_to_base64(fig)
