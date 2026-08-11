"""
app.py
------
Ứng dụng web (Streamlit) cho Đề tài 2: Tính toán thống kê từ file CSV.

Chức năng:
    1. Cho phép chọn/upload file CSV từ máy tính người dùng.
    2. Chọn cột số cần thống kê và (tùy chọn) cột để nhóm / cột ngày để
       xem xu hướng theo thời gian.
    3. Tính thống kê (mean/min/max/stddev) theo phương pháp streaming
       (chunksize) để xử lý được cả file rất lớn mà không tràn RAM.
    4. Trực quan hoá: biểu đồ cột theo nhóm, histogram phân phối,
       biểu đồ đường xu hướng theo thời gian, biểu đồ tròn tỉ trọng.
    5. Xuất báo cáo phân tích ra file HTML để tải về / nộp kèm đồ án.

Chạy chương trình:
    streamlit run app.py
"""

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from analytics import compute_overall_and_group_stats, compute_histogram, compute_trend_by_key
from charts import bar_chart_by_group, histogram_chart, line_chart_trend, pie_chart
from report_generator import build_html_report, save_html_report

st.set_page_config(page_title="Thống kê dữ liệu CSV lớn", layout="wide")

st.title("📊 Chương trình thống kê dữ liệu từ file CSV")
st.caption(
    "Đề tài: Tính toán thống kê từ file CSV lớn — Đọc dữ liệu theo chunk, "
    "tính trung bình/min/max, trực quan hoá và xuất báo cáo HTML."
)

# ---------------------------------------------------------------------------
# BƯỚC 1: Chọn file CSV từ máy tính
# ---------------------------------------------------------------------------
st.header("1️⃣ Chọn file dữ liệu")
uploaded_file = st.file_uploader("Chọn file CSV từ máy tính của bạn", type=["csv"])

if uploaded_file is None:
    st.info("👆 Hãy chọn một file CSV để bắt đầu phân tích (ví dụ: dữ liệu doanh thu theo ngày).")
    st.stop()

# Lưu file upload ra đĩa tạm (để đọc theo chunksize, tránh giữ toàn bộ file trong RAM)
tmp_dir = Path(tempfile.gettempdir()) / "thongke_csv_app"
tmp_dir.mkdir(exist_ok=True)
tmp_path = tmp_dir / uploaded_file.name
with open(tmp_path, "wb") as f:
    f.write(uploaded_file.getbuffer())

file_size_mb = tmp_path.stat().st_size / (1024 * 1024)
st.success(f"Đã tải lên: **{uploaded_file.name}** ({file_size_mb:.2f} MB)")

# Đọc thử vài dòng đầu để lấy danh sách cột + preview, không đọc cả file
preview_df = pd.read_csv(tmp_path, nrows=50)
with st.expander("Xem trước 50 dòng đầu tiên"):
    st.dataframe(preview_df, use_container_width=True)

all_columns = list(preview_df.columns)
numeric_like_cols = [
    c for c in all_columns
    if pd.to_numeric(preview_df[c], errors="coerce").notna().sum() > 0
]

# ---------------------------------------------------------------------------
# BƯỚC 2: Cấu hình phân tích
# ---------------------------------------------------------------------------
st.header("2️⃣ Cấu hình phân tích")
col1, col2, col3 = st.columns(3)

with col1:
    value_column = st.selectbox("Cột số cần thống kê", numeric_like_cols)
with col2:
    group_options = ["(không nhóm)"] + [c for c in all_columns if c != value_column]
    group_col = st.selectbox("Cột để nhóm (tuỳ chọn)", group_options)
    group_col = None if group_col == "(không nhóm)" else group_col
with col3:
    date_options = ["(không có)"] + [c for c in all_columns if c != value_column]
    date_col = st.selectbox("Cột thời gian để xem xu hướng (tuỳ chọn)", date_options)
    date_col = None if date_col == "(không có)" else date_col

chunksize = st.slider("Kích thước chunk khi đọc file (số dòng/lần đọc)", 10_000, 500_000, 100_000, step=10_000)

run = st.button("🚀 Chạy phân tích", type="primary")

if not run:
    st.stop()

# ---------------------------------------------------------------------------
# BƯỚC 3: Tính toán thống kê (streaming theo chunk)
# ---------------------------------------------------------------------------
st.header("3️⃣ Kết quả thống kê")

with st.spinner("Đang đọc và tính toán thống kê..."):
    result = compute_overall_and_group_stats(
        str(tmp_path), value_column, group_by=group_col, chunksize=chunksize
    )

overall = result["overall"]
m1, m2, m3, m4 = st.columns(4)
m1.metric("Trung bình", f"{overall['mean']:,.2f}")
m2.metric("Nhỏ nhất", f"{overall['min']:,.2f}")
m3.metric("Lớn nhất", f"{overall['max']:,.2f}")
m4.metric("Độ lệch chuẩn", f"{overall['stddev']:,.2f}")

st.caption(
    f"Đã xử lý {result['rows_read']:,} dòng trong {result['elapsed_seconds']} giây "
    f"({overall['count_invalid']:,} dòng lỗi/thiếu bị bỏ qua)."
)

if group_col:
    st.subheader(f"Thống kê theo '{group_col}'")
    group_df = pd.DataFrame(result["by_group"]).T
    st.dataframe(group_df, use_container_width=True)

# ---------------------------------------------------------------------------
# BƯỚC 4: Trực quan hoá
# ---------------------------------------------------------------------------
st.header("4️⃣ Trực quan hoá dữ liệu")
charts_for_report = {}

if group_col:
    labels = list(result["by_group"].keys())
    means = [s["mean"] for s in result["by_group"].values()]
    counts = [s["count_valid"] for s in result["by_group"].values()]

    c1, c2 = st.columns(2)
    with c1:
        bar_img = bar_chart_by_group(labels, means, f"Trung bình {value_column} theo {group_col}", value_column)
        st.image(bar_img)
        charts_for_report[f"Trung bình {value_column} theo {group_col}"] = bar_img
    with c2:
        pie_img = pie_chart(labels, counts, f"Tỉ trọng số lượng bản ghi theo {group_col}")
        st.image(pie_img)
        charts_for_report[f"Tỉ trọng số lượng bản ghi theo {group_col}"] = pie_img

with st.spinner("Đang tính histogram phân phối dữ liệu..."):
    hist = compute_histogram(str(tmp_path), value_column, bins=25, chunksize=chunksize)
hist_img = histogram_chart(hist["edges"], hist["counts"], f"Phân phối giá trị của {value_column}", value_column)
st.image(hist_img)
charts_for_report[f"Phân phối giá trị của {value_column}"] = hist_img

if date_col:
    with st.spinner(f"Đang tính xu hướng theo '{date_col}'..."):
        trend = compute_trend_by_key(str(tmp_path), date_col, value_column, agg="sum", chunksize=chunksize)
    if trend["keys"]:
        trend_img = line_chart_trend(trend["keys"], trend["values"], f"Xu hướng tổng {value_column} theo {date_col}", value_column)
        st.image(trend_img)
        charts_for_report[f"Xu hướng tổng {value_column} theo {date_col}"] = trend_img

# ---------------------------------------------------------------------------
# BƯỚC 5: Xuất báo cáo HTML
# ---------------------------------------------------------------------------
st.header("5️⃣ Xuất báo cáo")

html_report = build_html_report(
    file_name=uploaded_file.name,
    column=value_column,
    result=result,
    charts=charts_for_report,
    group_by=group_col,
)

st.download_button(
    label="⬇️ Tải báo cáo HTML",
    data=html_report,
    file_name=f"bao_cao_{Path(uploaded_file.name).stem}.html",
    mime="text/html",
    type="primary",
)

with st.expander("Xem trước nội dung báo cáo HTML"):
    st.components.v1.html(html_report, height=600, scrolling=True)
