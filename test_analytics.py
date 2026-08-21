"""
test_analytics.py
------------------
Unit test cho analytics.py: dò encoding, histogram streaming.
"""

import pytest

from analytics import detect_encoding, compute_histogram, compute_overall_and_group_stats


class TestDetectEncoding:
    def test_utf8_file(self, normal_csv):
        assert detect_encoding(normal_csv) == "utf-8"

    def test_cp1252_file(self, cp1252_csv):
        enc = detect_encoding(cp1252_csv)
        assert enc != "utf-8"
        # Phải đọc được bằng encoding vừa dò ra, không lỗi
        import pandas as pd
        df = pd.read_csv(cp1252_csv, encoding=enc)
        assert len(df) == 3


class TestComputeHistogram:
    def test_basic_histogram_sums_to_valid_count(self, normal_csv):
        overall = compute_overall_and_group_stats(normal_csv, "doanh_thu", chunksize=1000)["overall"]
        hist = compute_histogram(
            normal_csv, "doanh_thu", bins=20,
            value_min=overall["min"], value_max=overall["max"], chunksize=1000,
        )
        assert sum(hist["counts"]) == overall["count_valid"]
        assert len(hist["edges"]) == 21  # bins + 1
        assert len(hist["counts"]) == 20

    def test_auto_detect_min_max_when_not_provided(self, normal_csv):
        """Nếu không truyền value_min/max, hàm phải tự quét 1 lượt để tìm."""
        hist = compute_histogram(normal_csv, "doanh_thu", bins=10, chunksize=1000)
        assert hist["edges"][0] < hist["edges"][-1]
        assert sum(hist["counts"]) > 0

    def test_degenerate_min_equals_max(self, same_value_csv):
        hist = compute_histogram(same_value_csv, "val", bins=25, value_min=100, value_max=100, chunksize=100)
        assert sum(hist["counts"]) == 500
        assert all(e == 100 for e in hist["edges"])

    def test_rounded_min_max_does_not_drop_boundary_values(self, csv_dir):
        """
        BUG (đã sửa): value_min/value_max truyền vào thường lấy từ thống kê
        tổng quan đã làm tròn 2 chữ số (vd overall["min"]). Nếu giá trị thật
        trong file có nhiều chữ số thập phân hơn, làm tròn có thể đẩy min
        lên cao hơn / max xuống thấp hơn giá trị thật -> np.histogram() âm
        thầm loại các giá trị "nằm ngoài" khoảng đã làm tròn.
        """
        import pandas as pd

        # Cố tình tạo giá trị min có nhiều chữ số thập phân, làm tròn sẽ tăng lên
        df = pd.DataFrame({"val": [1048.3783931497203, 200.0, 300.0, 499938.01799955696]})
        path = csv_dir / "rounding_edge.csv"
        df.to_csv(path, index=False)

        rounded_min = round(1048.3783931497203, 2)  # 1048.38 > giá trị thật
        rounded_max = round(499938.01799955696, 2)  # 499938.02

        hist = compute_histogram(str(path), "val", bins=10, value_min=rounded_min, value_max=rounded_max, chunksize=10)
        assert sum(hist["counts"]) == 4, "Giá trị biên bị làm tròn lệch không được phép mất khỏi histogram"


class TestComputeOverallAndGroupStatsWrapper:
    def test_wrapper_delegates_correctly(self, normal_csv):
        r1 = compute_overall_and_group_stats(normal_csv, "doanh_thu", group_by="khu_vuc", chunksize=1000)
        assert "by_group" in r1
        assert r1["overall"]["count_valid"] > 0

    def test_wrapper_passes_date_period(self, normal_csv):
        r = compute_overall_and_group_stats(
            normal_csv, "doanh_thu", extra_group_by="ngay", date_period="month", chunksize=1000
        )
        assert "trend" in r
        assert all(len(k) == 7 for k in r["trend"]["keys"])  # "YYYY-MM"
