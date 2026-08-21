"""
test_real_dataset.py
---------------------
Test tích hợp (integration test) chạy TOÀN BỘ pipeline với bộ dữ liệu thật
(Amazon Sale Report — 24 cột, ~129.000 dòng, nhiều tình huống thực tế: cột
thiếu dữ liệu, cột boolean, cột có cardinality cực cao, encoding, nhiều năm).

Các test này SKIP (không FAIL) nếu không tìm thấy file dữ liệu — đặt file
vào tests/data/Amazon_Sale_Report.csv hoặc khai báo qua biến môi trường
AMAZON_CSV_PATH để chạy đầy đủ:

    AMAZON_CSV_PATH=/duong/dan/Amazon_Sale_Report.csv pytest tests/test_real_dataset.py -v
"""

import time

import pytest

from analytics import compute_overall_and_group_stats, compute_histogram, detect_encoding
from charts import bar_chart_by_group, histogram_chart, line_chart_trend, pie_chart
from report_generator import build_html_report
from stats_pandas_chunk import DATE_PERIODS

pytestmark = pytest.mark.real_data


@pytest.fixture(scope="module")
def encoding(real_csv_path):
    return detect_encoding(real_csv_path)


class TestEachNumericColumn:
    """Mỗi cột số trong file làm value_column ít nhất 1 lần."""

    @pytest.mark.parametrize("column", ["index", "Qty", "Amount", "ship-postal-code", "B2B"])
    def test_column_as_value(self, real_csv_path, encoding, column):
        result = compute_overall_and_group_stats(
            real_csv_path, column, group_by="Category", chunksize=300_000, encoding=encoding
        )
        overall = result["overall"]
        assert overall["count_valid"] > 0
        assert overall["min"] <= overall["mean"] <= overall["max"]
        group_sum = sum(int(s["count_valid"]) for s in result["by_group"].values())
        assert group_sum == overall["count_valid"], f"Cột '{column}': tổng nhóm không khớp tổng toàn bộ"


class TestHighCardinalityGroup:
    """SKU có ~7000 giá trị khác nhau — stress test hiệu năng biểu đồ cột."""

    def test_sku_group_computes_fast(self, real_csv_path, encoding):
        t0 = time.perf_counter()
        result = compute_overall_and_group_stats(
            real_csv_path, "Amount", group_by="SKU", chunksize=300_000, encoding=encoding
        )
        elapsed = time.perf_counter() - t0
        assert len(result["by_group"]) > 1000
        assert elapsed < 15.0, f"Tính thống kê theo SKU mất {elapsed:.1f}s — quá chậm"

    def test_sku_bar_chart_stays_fast_and_valid(self, real_csv_path, encoding):
        """BUG (đã sửa): vẽ bar chart với ~7000 cột từng mất ~50 giây."""
        result = compute_overall_and_group_stats(
            real_csv_path, "Amount", group_by="SKU", chunksize=300_000, encoding=encoding
        )
        labels = list(result["by_group"].keys())
        means = [s["mean"] for s in result["by_group"].values()]
        t0 = time.perf_counter()
        img = bar_chart_by_group(labels, means, "t", "v")
        elapsed = time.perf_counter() - t0
        assert img.startswith("data:image/png;base64,")
        assert elapsed < 5.0, f"Vẽ biểu đồ SKU mất {elapsed:.1f}s — có thể gây timeout hosting"


class TestMissingDataColumns:
    """Cột gần như toàn bộ thiếu dữ liệu (fulfilled-by) hoặc chỉ 1 giá trị (ship-country)."""

    def test_fulfilled_by_mostly_missing(self, real_csv_path, encoding):
        result = compute_overall_and_group_stats(
            real_csv_path, "Amount", group_by="fulfilled-by", chunksize=300_000, encoding=encoding
        )
        assert "(Thiếu dữ liệu)" in result["by_group"]
        group_sum = sum(int(s["count_valid"]) for s in result["by_group"].values())
        assert group_sum == result["overall"]["count_valid"]

    def test_ship_country_single_value(self, real_csv_path, encoding):
        result = compute_overall_and_group_stats(
            real_csv_path, "Amount", group_by="ship-country", chunksize=300_000, encoding=encoding
        )
        real_values = [k for k in result["by_group"] if k != "(Thiếu dữ liệu)"]
        assert len(real_values) == 1

    def test_courier_status_has_real_nan(self, real_csv_path, encoding):
        result = compute_overall_and_group_stats(
            real_csv_path, "Amount", group_by="Courier Status", chunksize=300_000, encoding=encoding
        )
        assert "(Thiếu dữ liệu)" in result["by_group"]
        group_sum = sum(int(s["count_valid"]) for s in result["by_group"].values())
        assert group_sum == result["overall"]["count_valid"]


class TestNumericColumnAsGroupReal:
    def test_postal_code_as_group_produces_string_labels(self, real_csv_path, encoding):
        """BUG (đã sửa): group_by trên cột số (ship-postal-code) từng crash charts.py."""
        result = compute_overall_and_group_stats(
            real_csv_path, "Amount", group_by="ship-postal-code", chunksize=300_000, encoding=encoding
        )
        labels = list(result["by_group"].keys())
        assert all(isinstance(lbl, str) for lbl in labels)
        # Không có nhãn nào dạng "123456.0" (phải bỏ đuôi .0)
        assert not any(lbl.endswith(".0") for lbl in labels)
        # Vẽ được bar chart không crash
        means = [s["mean"] for s in result["by_group"].values()]
        img = bar_chart_by_group(labels, means, "t", "v")
        assert img.startswith("data:image/png;base64,")


class TestAllDatePeriods:
    @pytest.mark.parametrize("period", DATE_PERIODS)
    def test_period_matches_overall_count(self, real_csv_path, encoding, period):
        result = compute_overall_and_group_stats(
            real_csv_path, "Amount", extra_group_by="Date", date_period=period,
            chunksize=300_000, encoding=encoding,
        )
        trend_sum = sum(result["trend"]["count"])
        assert trend_sum == result["overall"]["count_valid"]
        assert result["trend"]["keys"] == sorted(result["trend"]["keys"])

    def test_period_point_counts_decrease_with_coarser_granularity(self, real_csv_path, encoding):
        """Ngày > Tuần > Tháng > Quý > Năm về số điểm dữ liệu (kỳ càng dài, càng ít điểm)."""
        counts = {}
        for period in DATE_PERIODS:
            result = compute_overall_and_group_stats(
                real_csv_path, "Amount", extra_group_by="Date", date_period=period,
                chunksize=300_000, encoding=encoding,
            )
            counts[period] = len(result["trend"]["keys"])
        assert counts["day"] >= counts["week"] >= counts["month"] >= counts["quarter"] >= counts["year"]


class TestFullPipelineEndToEnd:
    """Toàn bộ luồng: đọc -> thống kê -> histogram -> 4 biểu đồ -> báo cáo HTML."""

    def test_full_pipeline_amount_category_date(self, real_csv_path, encoding):
        result = compute_overall_and_group_stats(
            real_csv_path, "Amount", group_by="Category", extra_group_by="Date",
            date_period="month", chunksize=300_000, encoding=encoding,
        )
        overall = result["overall"]
        hist = compute_histogram(
            real_csv_path, "Amount", bins=25, value_min=overall["min"], value_max=overall["max"],
            chunksize=300_000, encoding=encoding,
        )
        assert sum(hist["counts"]) == overall["count_valid"]

        labels = list(result["by_group"].keys())
        means = [s["mean"] for s in result["by_group"].values()]
        counts = [s["count_valid"] for s in result["by_group"].values()]

        charts = {
            "bar": bar_chart_by_group(labels, means, "t", "v"),
            "pie": pie_chart(labels, counts, "t"),
            "hist": histogram_chart(hist["edges"], hist["counts"], "t", "v"),
            "trend": line_chart_trend(result["trend"]["keys"], result["trend"]["sum"], "t", "v"),
        }
        for name, img in charts.items():
            assert img.startswith("data:image/png;base64,"), f"Biểu đồ {name} không hợp lệ"

        html = build_html_report("Amazon_Sale_Report.csv", "Amount", result, charts, group_by="Category")
        assert len(html) > 10_000
        assert "<script>" not in html.lower().replace("<script>alert", "")  # không có script lạ ngoài dữ liệu

    def test_known_business_figures(self, real_csv_path, encoding):
        """Chốt lại các con số nghiệp vụ đã xác nhận thủ công trong quá trình phát triển,
        để phát hiện ngay nếu có thay đổi logic tính toán làm sai lệch kết quả."""
        result = compute_overall_and_group_stats(
            real_csv_path, "Amount", group_by="Category", chunksize=300_000, encoding=encoding
        )
        overall = result["overall"]
        assert overall["count_valid"] == 121_180
        assert overall["count_invalid"] == 7_795
        assert round(overall["mean"], 2) == 648.56
        assert "Set" in result["by_group"]
        top_group = max(result["by_group"].items(), key=lambda kv: kv[1]["mean"])
        assert top_group[0] == "Set"
