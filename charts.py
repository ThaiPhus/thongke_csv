"""
charts.py
---------
Sinh các biểu đồ trực quan hoá bằng matplotlib, trả về chuỗi PNG
dạng base64 (data URI) để có thể:
    - hiển thị trực tiếp trong Streamlit (st.image)
    - nhúng thẳng vào file báo cáo HTML (không cần lưu file ảnh riêng)
"""

from __future__ import annotations

import base64
import io
from typing import Sequence

import matplotlib
matplotlib.use("Agg")  # backend không cần màn hình, phù hợp môi trường server
import matplotlib.pyplot as plt


def _fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def bar_chart_by_group(labels: Sequence[str], values: Sequence[float], title: str, ylabel: str) -> str:
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, values, color="#2E86AB")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=30)
    for b in bars:
        h = b.get_height()
        ax.annotate(f"{h:,.0f}", (b.get_x() + b.get_width() / 2, h),
                    ha="center", va="bottom", fontsize=8)
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
    ax.bar(edges[:-1], counts, width=widths, align="edge", color="#A23B72", edgecolor="white")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Số lượng bản ghi")

    if clipped:
        ax.set_xlim(edges[0], xlim_max)
        ax.text(
            0.99, 0.97,
            f"* Trục X thu gọn quanh {focus_percentile:.0f}% dữ liệu\n  (đã lược bớt vài giá trị ngoại lai)",
            transform=ax.transAxes, ha="right", va="top", fontsize=8, color="#666",
            bbox=dict(boxstyle="round", fc="white", ec="#ddd", alpha=0.9),
        )

    fig.tight_layout()
    return _fig_to_base64(fig)


def line_chart_trend(x_labels: Sequence[str], values: Sequence[float], title: str, ylabel: str) -> str:
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x_labels, values, color="#F18F01", marker="o", markersize=3, linewidth=1.5)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=45)
    # Chỉ hiện tối đa ~15 nhãn trục X để không bị rối khi có nhiều ngày
    step = max(1, len(x_labels) // 15)
    ax.set_xticks(range(0, len(x_labels), step))
    ax.set_xticklabels([x_labels[i] for i in range(0, len(x_labels), step)])
    fig.tight_layout()
    return _fig_to_base64(fig)


def pie_chart(labels: Sequence[str], values: Sequence[float], title: str, top_n: int = 6, min_label_pct: float = 3.0) -> str:
    """
    Vẽ biểu đồ tròn, GOM các nhóm nhỏ (ngoài top_n nhóm lớn nhất) vào một
    lát "Khác", và chỉ hiện % ngay trên lát bánh nếu lát đó đủ lớn
    (>= min_label_pct%) — tên nhóm được đưa ra chú thích (legend) bên cạnh
    thay vì ghi trực tiếp lên lát bánh, để tránh chữ chồng lên nhau khi có
    nhiều nhóm nhỏ.
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

    def _autopct(pct):
        return f"{pct:.1f}%" if pct >= min_label_pct else ""

    fig, ax = plt.subplots(figsize=(7, 5))
    wedges, _texts, _autotexts = ax.pie(
        plot_values,
        labels=None,
        autopct=_autopct,
        pctdistance=0.75,
        startangle=90,
        colors=plt.cm.Set2.colors,
    )
    ax.legend(
        wedges, plot_labels, title="Nhóm",
        loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9,
    )
    ax.set_title(title)
    ax.axis("equal")
    fig.tight_layout()
    return _fig_to_base64(fig)
