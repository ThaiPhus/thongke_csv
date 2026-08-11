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


def histogram_chart(edges: Sequence[float], counts: Sequence[int], title: str, xlabel: str) -> str:
    fig, ax = plt.subplots(figsize=(7, 4))
    widths = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
    ax.bar(edges[:-1], counts, width=widths, align="edge", color="#A23B72", edgecolor="white")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Số lượng bản ghi")
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


def pie_chart(labels: Sequence[str], values: Sequence[float], title: str) -> str:
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90,
           colors=plt.cm.Set2.colors)
    ax.set_title(title)
    fig.tight_layout()
    return _fig_to_base64(fig)
