"""
app.py
------
Ứng dụng web (Streamlit) cho Đề tài 2: Tính toán thống kê từ file CSV.

Chức năng:
    1. Chọn/upload file CSV từ máy tính người dùng (tự dò encoding, xử lý lỗi).
    2. Chọn cột số cần thống kê và (tùy chọn) cột để nhóm / cột ngày.
    3. Tính thống kê (tổng/mean/min/max/stddev) theo phương pháp streaming
       (chunksize) để xử lý được cả file rất lớn mà không tràn RAM.
    4. Trực quan hoá: biểu đồ cột theo nhóm, histogram phân phối,
       biểu đồ đường xu hướng theo thời gian, biểu đồ tròn tỉ trọng.
    5. Xuất báo cáo phân tích ra file HTML để tải về / nộp kèm đồ án.

Giao diện: hệ thiết kế Hallmark (xem tokens.css) — genre modern-minimal,
theme Cobalt (grotesk-sans + mono pairing, tông xanh lạnh, số liệu dùng
font mono cho cảm giác "công cụ kỹ thuật"). Cấu hình gom vào sidebar
(side-rail nav), kết quả hiển thị theo tab ở khu vực chính.

Chạy chương trình:
    streamlit run app.py
"""

import hashlib
import tempfile
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from analytics import compute_overall_and_group_stats, compute_histogram, detect_encoding
from charts import bar_chart_by_group, histogram_chart, line_chart_trend, pie_chart
from report_generator import build_html_report

st.set_page_config(page_title="Thống kê dữ liệu CSV lớn", page_icon="◆", layout="wide")

# ===========================================================================
# HỆ THIẾT KẾ (Hallmark · macrostructure: N/A (app) · genre: modern-minimal
# theme: Cobalt · nav: N3 side-rail · tone: technical)
# Token gốc portable ở tokens.css — khối dưới đây là bản inline để Streamlit
# render trực tiếp (Streamlit không tự load file CSS ngoài).
# ===========================================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {
        --color-paper: oklch(98.5% 0.003 240);
        --color-paper-2: oklch(96% 0.005 240);
        --color-paper-3: oklch(93% 0.008 240);
        --color-border: oklch(88% 0.006 240);
        --color-border-strong: oklch(78% 0.01 240);
        --color-ink: oklch(22% 0.015 250);
        --color-ink-soft: oklch(45% 0.012 250);
        --color-ink-faint: oklch(60% 0.01 250);
        --color-accent: oklch(52% 0.16 250);
        --color-accent-strong: oklch(42% 0.17 250);
        --color-accent-soft: oklch(94% 0.03 250);
        --color-success: oklch(60% 0.14 150);
        --color-warning: oklch(70% 0.15 80);
        --color-error: oklch(55% 0.19 25);
        --color-focus: oklch(60% 0.19 250);
        --font-display: 'Space Grotesk', sans-serif;
        --font-body: 'Inter', sans-serif;
        --font-mono: 'JetBrains Mono', monospace;
        --space-xs: 4px; --space-sm: 8px; --space-md: 16px;
        --space-lg: 24px; --space-xl: 32px; --space-2xl: 48px;
        --radius-sm: 6px; --radius-md: 10px; --radius-lg: 16px;
        --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
        --dur-fast: 120ms; --dur-base: 200ms;
    }

    html, body, [class*="css"] { font-family: var(--font-body); color: var(--color-ink); }
    .stApp { background: var(--color-paper); }
    .block-container { padding-top: var(--space-xl); padding-bottom: var(--space-2xl); max-width: 1180px; }

    /* ---- Typography ---- */
    h1, h2, h3, .app-title {
        font-family: var(--font-display) !important;
        font-weight: 600 !important;
        font-style: normal !important;
        letter-spacing: -0.01em;
        color: var(--color-ink) !important;
    }
    p, span, label, .stMarkdown { font-family: var(--font-body); }

    .app-eyebrow {
        font-family: var(--font-mono); font-size: 0.72rem; font-weight: 500;
        letter-spacing: 0.08em; text-transform: uppercase; color: var(--color-accent);
        margin-bottom: var(--space-xs);
    }
    .app-title { font-size: clamp(1.6rem, 2.4vw, 2.1rem); margin: 0 0 var(--space-xs) 0; line-height: 1.15; }
    .app-subtitle { color: var(--color-ink-soft); font-size: 0.95rem; margin: 0 0 var(--space-lg) 0; }

    /* ---- Sidebar (N3 side-rail) ---- */
    section[data-testid="stSidebar"] {
        background: var(--color-paper-2);
        border-right: 1px solid var(--color-border);
    }
    section[data-testid="stSidebar"] h3 {
        font-family: var(--font-mono) !important;
        font-size: 0.78rem !important; font-weight: 600 !important;
        letter-spacing: 0.06em; text-transform: uppercase;
        color: var(--color-ink-soft) !important;
        border-top: 1px solid var(--color-border);
        padding-top: var(--space-md); margin-top: var(--space-md) !important;
    }

    /* ---- Buttons: default / hover / focus-visible / active / disabled ---- */
    .stButton > button, .stDownloadButton > button {
        font-family: var(--font-body); font-weight: 600; border-radius: var(--radius-sm);
        border: 1px solid var(--color-border-strong);
        transition: background var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out);
    }
    .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
        background: var(--color-accent); border-color: var(--color-accent); color: white;
    }
    .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {
        background: var(--color-accent-strong); border-color: var(--color-accent-strong);
    }
    .stButton > button[kind="primary"]:active, .stDownloadButton > button[kind="primary"]:active {
        transform: translateY(1px);
    }
    .stButton > button:focus-visible, .stDownloadButton > button:focus-visible {
        outline: 2px solid var(--color-focus); outline-offset: 2px;
    }
    .stButton > button:disabled { opacity: 0.5; }

    /* ---- Tabs ---- */
    .stTabs [data-baseweb="tab-list"] { gap: var(--space-lg); border-bottom: 1px solid var(--color-border); }
    .stTabs [data-baseweb="tab"] {
        font-family: var(--font-mono); font-size: 0.78rem; font-weight: 500;
        letter-spacing: 0.04em; text-transform: uppercase;
        color: var(--color-ink-faint); padding: var(--space-sm) 0; background: transparent;
    }
    .stTabs [aria-selected="true"] { color: var(--color-accent) !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: var(--color-accent); height: 2px; }

    /* ---- File uploader (dropzone) ---- */
    [data-testid="stFileUploaderDropzone"] {
        background: var(--color-paper); border: 1.5px dashed var(--color-border-strong) !important;
        border-radius: var(--radius-md); transition: border-color var(--dur-base) var(--ease-out);
    }
    [data-testid="stFileUploaderDropzone"]:hover { border-color: var(--color-accent) !important; }

    /* ---- Alerts / status boxes ---- */
    div[data-testid="stAlert"] { border-radius: var(--radius-md); border: 1px solid var(--color-border); }

    /* ---- Dataframe / expander ---- */
    [data-testid="stExpander"] { border: 1px solid var(--color-border); border-radius: var(--radius-md); }
    [data-testid="stDataFrame"] { border: 1px solid var(--color-border); border-radius: var(--radius-sm); }

    /* ---- Stat cards (thay cho st.metric mặc định) ---- */
    .stat-grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: var(--space-md); margin: var(--space-md) 0 var(--space-lg) 0;
    }
    .stat-card {
        background: white; border: 1px solid var(--color-border); border-radius: var(--radius-md);
        padding: var(--space-md) var(--space-lg); border-top: 3px solid var(--color-accent);
    }
    .stat-card .stat-label {
        font-family: var(--font-mono); font-size: 0.7rem; font-weight: 500;
        letter-spacing: 0.06em; text-transform: uppercase; color: var(--color-ink-faint);
        margin-bottom: var(--space-xs);
    }
    .stat-card .stat-value {
        font-family: var(--font-mono); font-size: 1.5rem; font-weight: 600;
        color: var(--color-ink); line-height: 1.2; overflow-wrap: anywhere;
    }

    /* ---- Section step label ---- */
    .step-label {
        font-family: var(--font-mono); font-size: 0.72rem; font-weight: 600;
        color: var(--color-accent); letter-spacing: 0.05em;
    }

    :focus-visible { outline: 2px solid var(--color-focus); outline-offset: 2px; }

    @media (prefers-reduced-motion: reduce) {
        * { transition-duration: 0.001ms !important; animation-duration: 0.001ms !important; }
    }

    @media (max-width: 480px) {
        .stat-grid { grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); }
        .stat-card .stat-value { font-size: 1.2rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _stat_cards_html(items: list[tuple[str, str]]) -> str:
    """Render một hàng thẻ số liệu kiểu dashboard kỹ thuật (số dùng font mono)."""
    cards = "".join(
        f'<div class="stat-card"><div class="stat-label">{label}</div>'
        f'<div class="stat-value">{value}</div></div>'
        for label, value in items
    )
    return f'<div class="stat-grid">{cards}</div>'


TMP_DIR = Path(tempfile.gettempdir()) / "thongke_csv_app"
TMP_DIR.mkdir(exist_ok=True)
KEEP_LAST_N_FILES = 3  # chỉ giữ lại file tạm của vài lượt upload gần nhất, tránh phình dung lượng hosting


def _cleanup_old_temp_files(keep_path: Path) -> None:
    """Xoá bớt các file tạm cũ (giữ lại KEEP_LAST_N_FILES file gần nhất) để không chiếm dung lượng đĩa trên hosting."""
    try:
        files = sorted(
            [p for p in TMP_DIR.glob("*") if p.is_file() and p != keep_path],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old_file in files[max(0, KEEP_LAST_N_FILES - 1):]:
            old_file.unlink(missing_ok=True)
    except Exception:
        pass  # dọn dẹp thất bại không nên làm gián đoạn trải nghiệm người dùng


@st.cache_data(show_spinner=False)
def _cached_detect_encoding(file_hash, file_path):
    return detect_encoding(file_path)


@st.cache_data(show_spinner=False)
def _cached_preview(file_hash, file_path, encoding):
    return pd.read_csv(file_path, nrows=50, encoding=encoding)


@st.cache_data(show_spinner=False)
def _cached_overall_and_group_stats(file_hash, file_path, column, group_by, extra_group_by, chunksize, encoding):
    return compute_overall_and_group_stats(
        file_path, column, group_by=group_by, extra_group_by=extra_group_by,
        chunksize=chunksize, encoding=encoding,
    )


@st.cache_data(show_spinner=False)
def _cached_histogram(file_hash, file_path, column, bins, value_min, value_max, chunksize, encoding):
    return compute_histogram(
        file_path, column, bins=bins, value_min=value_min, value_max=value_max,
        chunksize=chunksize, encoding=encoding,
    )


# ===========================================================================
# SIDEBAR: chọn file + cấu hình phân tích
# ===========================================================================
with st.sidebar:
    st.markdown('<div class="app-eyebrow">Đồ án · Phân tích dữ liệu lớn</div>', unsafe_allow_html=True)
    st.markdown('<div class="app-title" style="font-size:1.3rem;">Cấu hình</div>', unsafe_allow_html=True)

    st.markdown('<div class="step-label">01 · DỮ LIỆU</div>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Kéo-thả hoặc chọn file CSV từ máy tính",
        type=["csv"],
        help="Hỗ trợ file CSV dung lượng lớn, tự động dò encoding (UTF-8/Latin-1/CP1252).",
    )

    if uploaded_file is None:
        st.info("Hãy chọn một file CSV để bắt đầu.")
        st.stop()

    # --- Đọc & lưu file tạm, có xử lý lỗi rõ ràng ---
    file_bytes = uploaded_file.getvalue()
    if len(file_bytes) == 0:
        st.error("File rỗng, vui lòng chọn file khác.")
        st.stop()

    file_hash = hashlib.md5(file_bytes).hexdigest()
    tmp_path = TMP_DIR / f"{file_hash}_{uploaded_file.name}"

    if not tmp_path.exists():
        with st.spinner("Đang lưu file..."):
            t0 = time.perf_counter()
            with open(tmp_path, "wb") as f:
                f.write(file_bytes)
            save_time = time.perf_counter() - t0
        _cleanup_old_temp_files(tmp_path)
    else:
        save_time = 0.0

    file_size_mb = tmp_path.stat().st_size / (1024 * 1024)

    # --- Dò encoding + đọc preview, có xử lý lỗi ---
    try:
        with st.spinner("Đang dò định dạng file..."):
            encoding = _cached_detect_encoding(file_hash, str(tmp_path))
            preview_df = _cached_preview(file_hash, str(tmp_path), encoding)
    except pd.errors.EmptyDataError:
        st.error("File CSV không có dữ liệu hoặc thiếu dòng tiêu đề (header).")
        st.stop()
    except pd.errors.ParserError as e:
        st.error(f"File CSV bị lỗi định dạng, không thể đọc được: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Không thể đọc file: {e}")
        st.stop()

    st.success(f"**{uploaded_file.name}**\n\n{file_size_mb:.2f} MB · {len(preview_df.columns)} cột · encoding: `{encoding}`")

    if file_size_mb > 80:
        st.warning(
            "File khá lớn so với hosting miễn phí (thường 1 CPU/~1GB RAM). "
            "Nếu chạy chậm: tăng kích thước chunk hoặc tắt histogram bên dưới."
        )

    with st.expander("Xem trước 50 dòng đầu"):
        st.dataframe(preview_df, width="stretch")

    all_columns = list(preview_df.columns)
    numeric_like_cols = [
        c for c in all_columns
        if pd.to_numeric(preview_df[c], errors="coerce").notna().sum() > 0
    ]

    if not numeric_like_cols:
        st.error("Không tìm thấy cột số nào trong file để thống kê.")
        st.stop()

    st.markdown('<div class="step-label">02 · CỘT PHÂN TÍCH</div>', unsafe_allow_html=True)
    value_column = st.selectbox("Cột số cần thống kê", numeric_like_cols)

    group_options = ["(không nhóm)"] + [c for c in all_columns if c != value_column]
    group_col = st.selectbox("Cột để nhóm (tuỳ chọn)", group_options)
    group_col = None if group_col == "(không nhóm)" else group_col

    date_options = ["(không có)"] + [c for c in all_columns if c != value_column]
    date_col = st.selectbox("Cột thời gian để xem xu hướng (tuỳ chọn)", date_options)
    date_col = None if date_col == "(không có)" else date_col

    st.markdown('<div class="step-label">03 · TUỲ CHỌN NÂNG CAO</div>', unsafe_allow_html=True)
    chunksize = st.slider("Kích thước chunk (số dòng/lần đọc)", 50_000, 1_000_000, 300_000, step=50_000)
    want_histogram = st.checkbox("Tính histogram phân phối", value=True)

    run = st.button("Chạy phân tích", type="primary", width="stretch")

    if run:
        st.session_state["analysis_params"] = dict(
            file_hash=file_hash, tmp_path=str(tmp_path), encoding=encoding,
            value_column=value_column, group_col=group_col, date_col=date_col,
            chunksize=chunksize, want_histogram=want_histogram,
            file_name=uploaded_file.name,
        )

# ===========================================================================
# KHU VỰC CHÍNH: kết quả phân tích (dùng session_state để giữ kết quả khi
# chuyển tab / tương tác khác, không phải bấm lại "Chạy phân tích")
# ===========================================================================
st.markdown('<div class="app-eyebrow">Đề tài 2 · CN Phân tích dữ liệu lớn</div>', unsafe_allow_html=True)
st.markdown('<div class="app-title">Thống kê dữ liệu từ file CSV</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Đọc dữ liệu lớn theo chunk, tính thống kê, trực quan hoá và xuất báo cáo HTML.</div>',
    unsafe_allow_html=True,
)

if "analysis_params" not in st.session_state:
    st.info("Cấu hình và bấm **Chạy phân tích** ở thanh bên trái để bắt đầu.")
    st.stop()

p = st.session_state["analysis_params"]

try:
    with st.spinner("Đang đọc và tính toán (lượt quét 1/…)..."):
        result = _cached_overall_and_group_stats(
            p["file_hash"], p["tmp_path"], p["value_column"], p["group_col"],
            p["date_col"], p["chunksize"], p["encoding"],
        )
except Exception as e:
    st.error(f"Lỗi khi tính toán thống kê: {e}")
    st.stop()

overall = result["overall"]

if overall["count_valid"] == 0:
    st.error(f"Cột **{p['value_column']}** không có giá trị số hợp lệ nào để thống kê.")
    st.stop()

hist = None
if p["want_histogram"]:
    with st.spinner("Đang tính histogram (lượt quét 2/…)..."):
        hist = _cached_histogram(
            p["file_hash"], p["tmp_path"], p["value_column"], 25,
            overall["min"], overall["max"], p["chunksize"], p["encoding"],
        )

tab1, tab2, tab3 = st.tabs(["THỐNG KÊ TỔNG QUAN", "BIỂU ĐỒ TRỰC QUAN", "XUẤT BÁO CÁO"])

# --- TAB 1: Thống kê tổng quan ---
with tab1:
    st.markdown(
        _stat_cards_html([
            ("Tổng", f"{overall['sum']:,.0f}"),
            ("Trung bình", f"{overall['mean']:,.2f}"),
            ("Nhỏ nhất", f"{overall['min']:,.2f}"),
            ("Lớn nhất", f"{overall['max']:,.2f}"),
            ("Độ lệch chuẩn", f"{overall['stddev']:,.2f}"),
        ]),
        unsafe_allow_html=True,
    )

    st.caption(
        f"Đã xử lý {result['rows_read']:,} dòng trong {result['elapsed_seconds']} giây "
        f"({overall['count_invalid']:,} dòng lỗi/thiếu bị bỏ qua)."
    )

    if p["group_col"]:
        st.markdown(f"##### Thống kê theo '{p['group_col']}'")
        group_df = pd.DataFrame(result["by_group"]).T
        st.dataframe(group_df, width="stretch")

# --- TAB 2: Biểu đồ ---
charts_for_report = {}
with tab2:
    if p["group_col"]:
        labels = list(result["by_group"].keys())
        means = [s["mean"] for s in result["by_group"].values()]
        counts = [s["count_valid"] for s in result["by_group"].values()]

        c1, c2 = st.columns(2)
        with c1:
            bar_img = bar_chart_by_group(labels, means, f"Trung bình {p['value_column']} theo {p['group_col']}", p["value_column"])
            st.image(bar_img)
            charts_for_report[f"Trung bình {p['value_column']} theo {p['group_col']}"] = bar_img
        with c2:
            pie_img = pie_chart(labels, counts, f"Tỉ trọng số lượng bản ghi theo {p['group_col']}")
            st.image(pie_img)
            charts_for_report[f"Tỉ trọng số lượng bản ghi theo {p['group_col']}"] = pie_img

    if hist is not None:
        hist_img = histogram_chart(hist["edges"], hist["counts"], f"Phân phối giá trị của {p['value_column']}", p["value_column"])
        st.image(hist_img)
        charts_for_report[f"Phân phối giá trị của {p['value_column']}"] = hist_img

    if p["date_col"] and "trend" in result and result["trend"]["keys"]:
        trend = result["trend"]
        trend_img = line_chart_trend(trend["keys"], trend["sum"], f"Xu hướng tổng {p['value_column']} theo {p['date_col']}", p["value_column"])
        st.image(trend_img)
        charts_for_report[f"Xu hướng tổng {p['value_column']} theo {p['date_col']}"] = trend_img

    if not charts_for_report:
        st.info("Chưa có biểu đồ nào — hãy chọn cột nhóm/thời gian hoặc bật histogram ở thanh bên trái.")

# --- TAB 3: Xuất báo cáo ---
with tab3:
    html_report = build_html_report(
        file_name=p["file_name"],
        column=p["value_column"],
        result=result,
        charts=charts_for_report,
        group_by=p["group_col"],
    )

    st.download_button(
        label="Tải báo cáo HTML",
        data=html_report,
        file_name=f"bao_cao_{Path(p['file_name']).stem}.html",
        mime="text/html",
        type="primary",
    )

    with st.expander("Xem trước nội dung báo cáo"):
        st.components.v1.html(html_report, height=600, scrolling=True)
