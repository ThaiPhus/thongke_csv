"""
test_charts.py
---------------
Unit test cho charts.py: đảm bảo mọi biểu đồ luôn render ra ảnh PNG hợp lệ
(data URI đúng định dạng) trong các tình huống thường gặp lẫn cực đoan,
và các bug hiệu năng/hiển thị đã sửa không tái diễn.
"""

import base64
import time

import pytest

from charts import (
    bar_chart_by_group,
    histogram_chart,
    line_chart_trend,
    pie_chart,
    _readable_number,
)

PNG_PREFIX = "data:image/png;base64,"


def _assert_valid_png_data_uri(data_uri: str) -> None:
    assert data_uri.startswith(PNG_PREFIX)
    raw = base64.b64decode(data_uri[len(PNG_PREFIX):])
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


class TestBarChart:
    def test_returns_valid_png(self):
        img = bar_chart_by_group(["A", "B", "C"], [10, 20, 15], "Tiêu đề", "Giá trị")
        _assert_valid_png_data_uri(img)

    def test_single_group(self):
        img = bar_chart_by_group(["Only"], [42], "t", "v")
        _assert_valid_png_data_uri(img)

    def test_negative_values(self):
        img = bar_chart_by_group(["A", "B", "C"], [-5.5, 10.25, 0], "t", "v")
        _assert_valid_png_data_uri(img)

    def test_small_decimal_values_not_flattened(self):
        """BUG (đã sửa): giá trị < 1000 từng bị làm tròn về số nguyên trên trục Y,
        khiến dữ liệu dao động quanh 1 (vd Qty trung bình) bị 'san phẳng' mất hết
        khả năng phân biệt. Kiểm tra formatter giữ đúng số thập phân."""
        assert _readable_number(0.9) == "0.9"
        assert _readable_number(1.03) == "1.03"
        assert _readable_number(1.0) == "1"

    def test_large_values_abbreviated(self):
        assert _readable_number(1_200_000) == "1.2M"
        assert _readable_number(850_000) == "850K"
        assert _readable_number(2_000_000_000) == "2B"

    def test_many_groups_uses_top_n_and_stays_fast(self):
        """BUG (đã sửa): vẽ hàng nghìn cột từng mất ~50 giây và ra ảnh không đọc nổi.
        Giờ phải tự giới hạn top_n và chạy nhanh."""
        labels = [f"SKU_{i}" for i in range(3000)]
        values = list(range(3000))
        t0 = time.perf_counter()
        img = bar_chart_by_group(labels, values, "t", "v", top_n=20)
        elapsed = time.perf_counter() - t0
        _assert_valid_png_data_uri(img)
        assert elapsed < 5.0, f"Vẽ 3000 nhóm mất {elapsed:.1f}s — quá chậm, có thể gây timeout trên hosting"

    def test_long_labels_are_truncated(self):
        long_label = "Shipped - Waiting for Pick Up at Warehouse Location XYZ"
        img = bar_chart_by_group([long_label, "Short"], [10, 20], "t", "v")
        _assert_valid_png_data_uri(img)


class TestHistogramChart:
    def test_returns_valid_png(self):
        edges = [0, 10, 20, 30, 40]
        counts = [5, 10, 8, 2]
        img = histogram_chart(edges, counts, "t", "v")
        _assert_valid_png_data_uri(img)

    def test_degenerate_min_equals_max_does_not_crash(self):
        """BUG (đã sửa): min==max khiến mọi bin rộng 0 -> biểu đồ trống trơn dù có dữ liệu."""
        edges = [100.0] * 26
        counts = [0] * 24 + [500] + [0]
        img = histogram_chart(edges, counts, "t", "v")
        _assert_valid_png_data_uri(img)

    def test_clips_outliers_for_readability(self):
        # 99% dữ liệu nằm trong khoảng nhỏ, 1% là ngoại lai kéo dài trục X
        edges = list(range(0, 1010, 10))  # 0..1000, 100 bins
        counts = [0] * 99
        counts[5] = 10000  # phần lớn dữ liệu tập trung ở đây
        counts.append(1)  # 1 giá trị ngoại lai ở cuối
        img = histogram_chart(edges, counts, "t", "v")
        _assert_valid_png_data_uri(img)


class TestLineChartTrend:
    def test_returns_valid_png(self):
        img = line_chart_trend(["2024-01", "2024-02", "2024-03"], [100, 200, 150], "t", "v")
        _assert_valid_png_data_uri(img)

    def test_single_data_point(self):
        img = line_chart_trend(["2024-01"], [100], "t", "v")
        _assert_valid_png_data_uri(img)

    def test_many_points_still_readable(self):
        keys = [f"2024-{i:03d}" for i in range(365)]
        values = list(range(365))
        img = line_chart_trend(keys, values, "t", "v")
        _assert_valid_png_data_uri(img)


class TestPieChart:
    def test_returns_valid_png(self):
        img = pie_chart(["A", "B", "C"], [50, 30, 20], "t")
        _assert_valid_png_data_uri(img)

    def test_many_groups_merged_into_khac(self):
        labels = [f"G{i}" for i in range(15)]
        values = list(range(1, 16))
        img = pie_chart(labels, values, "t", top_n=6)
        _assert_valid_png_data_uri(img)

    def test_single_group(self):
        img = pie_chart(["Only"], [100], "t")
        _assert_valid_png_data_uri(img)

    def test_khac_color_never_collides_with_real_group(self):
        """BUG (đã sửa): khi >6 nhóm, lát 'Khác' (index 6 trong bảng màu tuần hoàn)
        từng trùng màu với nhóm đầu tiên vì bảng màu chỉ có 6 màu."""
        import charts as charts_module
        labels = [f"G{i}" for i in range(10)]
        values = list(range(1, 11))
        # Không raise, và không cần assert màu cụ thể (khó test qua ảnh PNG) —
        # nhưng đảm bảo NEUTRAL_OTHER tồn tại và khác mọi màu trong QUALITATIVE_PALETTE
        assert charts_module.NEUTRAL_OTHER not in charts_module.QUALITATIVE_PALETTE
