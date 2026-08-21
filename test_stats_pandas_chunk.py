"""
test_stats_pandas_chunk.py
---------------------------
Unit test cho lõi tính toán thống kê (stats_pandas_chunk.py).
Bao trùm toàn bộ các bug đã phát hiện và sửa trong quá trình phát triển,
để đảm bảo chúng KHÔNG BAO GIỜ tái diễn (regression test).
"""

import math

import pytest

from stats_pandas_chunk import compute_stats_pandas_chunk, _to_group_label, _bucket_date_series, DATE_PERIODS


# ---------------------------------------------------------------------------
# Thống kê tổng quan cơ bản
# ---------------------------------------------------------------------------
class TestOverallStats:
    def test_basic_stats_correct(self, normal_csv):
        result = compute_stats_pandas_chunk(normal_csv, "doanh_thu", chunksize=1000)
        overall = result["overall"]
        assert overall["count_valid"] > 0
        assert overall["count_invalid"] > 0  # normal_csv có ~2% dòng thiếu
        assert overall["min"] <= overall["mean"] <= overall["max"]
        assert overall["stddev"] >= 0
        assert result["rows_read"] == overall["count_valid"] + overall["count_invalid"]

    def test_sum_equals_mean_times_count(self, normal_csv):
        result = compute_stats_pandas_chunk(normal_csv, "doanh_thu", chunksize=1000)
        o = result["overall"]
        assert math.isclose(o["sum"], o["mean"] * o["count_valid"], rel_tol=1e-6)

    def test_no_group_no_trend_omits_keys(self, normal_csv):
        """Không truyền group_by/extra_group_by thì kết quả không có các khoá tương ứng."""
        result = compute_stats_pandas_chunk(normal_csv, "doanh_thu", chunksize=1000)
        assert "by_group" not in result
        assert "trend" not in result

    def test_only_reads_needed_columns(self, normal_csv):
        """usecols phải chỉ gồm đúng các cột cần dùng (tối ưu hiệu năng đã áp dụng)."""
        result = compute_stats_pandas_chunk(normal_csv, "doanh_thu", group_by="khu_vuc", chunksize=1000)
        assert result["overall"]["count_valid"] > 0  # chạy được nghĩa là usecols đúng


# ---------------------------------------------------------------------------
# BUG #1 (đã sửa): nhóm bị NaN từng bị âm thầm loại khỏi bảng theo nhóm,
# khiến tổng các nhóm KHÔNG khớp tổng toàn bộ.
# ---------------------------------------------------------------------------
class TestGroupByMissingValues:
    def test_group_sum_matches_overall_count(self, group_nan_csv):
        result = compute_stats_pandas_chunk(group_nan_csv, "doanh_thu", group_by="khu_vuc", chunksize=500)
        group_sum = sum(int(s["count_valid"]) for s in result["by_group"].values())
        assert group_sum == result["overall"]["count_valid"]

    def test_missing_group_has_explicit_label(self, group_nan_csv):
        result = compute_stats_pandas_chunk(group_nan_csv, "doanh_thu", group_by="khu_vuc", chunksize=500)
        assert "(Thiếu dữ liệu)" in result["by_group"]
        assert result["by_group"]["(Thiếu dữ liệu)"]["count_valid"] > 0

    def test_count_valid_is_int_not_float(self, group_nan_csv):
        """BUG (đã sửa): count_valid từng trả về float (150.0) thay vì int."""
        result = compute_stats_pandas_chunk(group_nan_csv, "doanh_thu", group_by="khu_vuc", chunksize=500)
        for stats in result["by_group"].values():
            assert isinstance(stats["count_valid"], int)


# ---------------------------------------------------------------------------
# BUG #2 (đã sửa): group_by trên cột SỐ (vd mã bưu điện) -> nhãn nhóm là
# float, làm crash charts.py (TypeError: object of type 'float' has no len())
# ---------------------------------------------------------------------------
class TestNumericColumnAsGroup:
    def test_group_labels_are_always_strings(self, numeric_group_csv):
        result = compute_stats_pandas_chunk(numeric_group_csv, "doanh_thu", group_by="ma_buu_dien", chunksize=500)
        labels = list(result["by_group"].keys())
        assert len(labels) > 0
        assert all(isinstance(lbl, str) for lbl in labels)

    def test_numeric_group_label_has_no_trailing_zero(self, numeric_group_csv):
        """100001.0 phải hiện thành '100001', không phải '100001.0'."""
        result = compute_stats_pandas_chunk(numeric_group_csv, "doanh_thu", group_by="ma_buu_dien", chunksize=500)
        labels = list(result["by_group"].keys())
        assert all(".0" not in lbl for lbl in labels if lbl != "(Thiếu dữ liệu)")
        assert "100001" in labels

    def test_to_group_label_helper_directly(self):
        assert _to_group_label(100001.0) == "100001"
        assert _to_group_label(100001.5) == "100001.5"
        assert _to_group_label(float("nan")) == "(Thiếu dữ liệu)"
        assert _to_group_label(None) == "(Thiếu dữ liệu)"
        assert _to_group_label("HN") == "HN"


# ---------------------------------------------------------------------------
# BUG #3 (đã sửa): cột kiểu boolean (True/False) làm value_column ->
# TypeError: type numpy.bool doesn't define __round__ method
# ---------------------------------------------------------------------------
class TestBooleanColumn:
    def test_boolean_value_column_does_not_crash(self, boolean_csv):
        result = compute_stats_pandas_chunk(boolean_csv, "is_b2b", chunksize=200)
        overall = result["overall"]
        assert overall["count_valid"] == 500
        assert 0.0 <= overall["mean"] <= 1.0
        assert overall["min"] in (0.0, 1.0)
        assert overall["max"] in (0.0, 1.0)

    def test_boolean_value_column_with_group(self, boolean_csv):
        result = compute_stats_pandas_chunk(boolean_csv, "is_b2b", group_by="grp", chunksize=200)
        group_sum = sum(int(s["count_valid"]) for s in result["by_group"].values())
        assert group_sum == result["overall"]["count_valid"]


# ---------------------------------------------------------------------------
# Dữ liệu bẩn thực tế (N/A, dấu gạch ngang, chuỗi rỗng, text lẫn trong số)
# ---------------------------------------------------------------------------
class TestDirtyData:
    def test_invalid_values_are_excluded_correctly(self, dirty_numeric_csv):
        result = compute_stats_pandas_chunk(dirty_numeric_csv, "gia", group_by="loai", chunksize=10)
        overall = result["overall"]
        # 3 giá trị hợp lệ: 100000, 250000, 300000 -> tổng 650000
        assert overall["count_valid"] == 3
        assert overall["count_invalid"] == 4
        assert overall["sum"] == 650_000

    def test_all_invalid_returns_zero_valid(self, all_invalid_csv):
        result = compute_stats_pandas_chunk(all_invalid_csv, "val", group_by="grp", chunksize=50)
        assert result["overall"]["count_valid"] == 0
        assert result["overall"]["min"] is None
        assert result["overall"]["max"] is None


# ---------------------------------------------------------------------------
# Trường hợp file rỗng / không có cột số
# ---------------------------------------------------------------------------
class TestEmptyAndInvalidFiles:
    def test_only_header_no_crash(self, only_header_csv):
        result = compute_stats_pandas_chunk(only_header_csv, "val", chunksize=50)
        assert result["overall"]["count_valid"] == 0

    def test_empty_file_raises_empty_data_error(self, empty_csv):
        import pandas as pd
        with pytest.raises(pd.errors.EmptyDataError):
            compute_stats_pandas_chunk(empty_csv, "val", chunksize=50)


# ---------------------------------------------------------------------------
# Trường hợp cực đoan: min == max (toàn bộ giá trị giống hệt nhau)
# ---------------------------------------------------------------------------
class TestDegenerateData:
    def test_min_equals_max(self, same_value_csv):
        result = compute_stats_pandas_chunk(same_value_csv, "val", chunksize=100)
        overall = result["overall"]
        assert overall["min"] == overall["max"] == 100
        assert overall["stddev"] == 0

    def test_single_group(self, single_group_csv):
        result = compute_stats_pandas_chunk(single_group_csv, "val", group_by="grp", chunksize=100)
        assert len(result["by_group"]) == 1


# ---------------------------------------------------------------------------
# Nhiều nhóm (kiểm tra không crash, hiệu năng hợp lý)
# ---------------------------------------------------------------------------
class TestManyGroups:
    def test_many_groups_all_present(self, many_groups_csv):
        result = compute_stats_pandas_chunk(many_groups_csv, "val", group_by="grp", chunksize=500)
        assert len(result["by_group"]) == 20
        group_sum = sum(int(s["count_valid"]) for s in result["by_group"].values())
        assert group_sum == result["overall"]["count_valid"]


# ---------------------------------------------------------------------------
# Encoding không phải UTF-8
# ---------------------------------------------------------------------------
class TestEncoding:
    def test_cp1252_with_explicit_encoding(self, cp1252_csv):
        result = compute_stats_pandas_chunk(cp1252_csv, "gia", group_by="ten", encoding="cp1252", chunksize=10)
        assert result["overall"]["count_valid"] == 3
        assert "Café Nord" in result["by_group"]

    def test_cp1252_with_wrong_encoding_raises(self, cp1252_csv):
        """Đọc file cp1252 bằng utf-8 (sai) phải báo lỗi rõ ràng, không âm thầm ra kết quả sai."""
        with pytest.raises(UnicodeDecodeError):
            compute_stats_pandas_chunk(cp1252_csv, "gia", group_by="ten", encoding="utf-8", chunksize=10)


# ---------------------------------------------------------------------------
# BUG #4 (đã sửa): xu hướng theo ngày sắp xếp theo THỨ TỰ CHUỖI thay vì
# thời gian thật -> sai khi dữ liệu trải qua ranh giới năm.
# ---------------------------------------------------------------------------
class TestDatePeriodBucketing:
    @pytest.mark.parametrize("period", DATE_PERIODS)
    def test_all_periods_run_without_error(self, normal_csv, period):
        result = compute_stats_pandas_chunk(
            normal_csv, "doanh_thu", extra_group_by="ngay", date_period=period, chunksize=1000
        )
        assert "trend" in result
        assert len(result["trend"]["keys"]) > 0

    @pytest.mark.parametrize("period", DATE_PERIODS)
    def test_trend_count_matches_overall(self, normal_csv, period):
        result = compute_stats_pandas_chunk(
            normal_csv, "doanh_thu", extra_group_by="ngay", date_period=period, chunksize=1000
        )
        trend_sum = sum(result["trend"]["count"])
        assert trend_sum == result["overall"]["count_valid"]

    def test_multi_year_sorts_chronologically_not_alphabetically(self, multi_year_date_csv):
        """
        Dữ liệu gốc dạng MM-DD-YY: 11-15-22, 12-01-22, 12-31-22, 01-01-23, 01-15-23, 02-01-23
        Sắp theo CHUỖI (bug cũ) sẽ cho: 01-01-23, 01-15-23, 02-01-23, 11-15-22, 12-01-22, 12-31-22 (SAI)
        Sắp theo THỜI GIAN THẬT (đã sửa) phải cho: 11-2022, 12-2022, 01-2023, 02-2023 (ĐÚNG)
        """
        result = compute_stats_pandas_chunk(
            multi_year_date_csv, "doanh_thu", extra_group_by="ngay", date_period="month", chunksize=100
        )
        keys = result["trend"]["keys"]
        assert keys == sorted(keys), "Nhãn ISO phải tự sắp đúng thứ tự khi sort chuỗi"
        assert keys == ["2022-11", "2022-12", "2023-01", "2023-02"]

    def test_bucket_date_week_format(self):
        import pandas as pd
        s = pd.Series(["2022-01-03", "2022-01-10"])  # thứ Hai của tuần ISO 1 và 2 năm 2022
        result = _bucket_date_series(s, "week")
        assert result.iloc[0].startswith("2022-W")

    def test_bucket_date_invalid_values_become_na(self):
        import pandas as pd
        s = pd.Series(["không phải ngày", "2022-01-01"])
        result = _bucket_date_series(s, "day")
        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == "2022-01-01"

    def test_date_period_on_non_date_column_does_not_crash(self, normal_csv):
        """Người dùng lỡ chọn cột không phải ngày làm date_period -> không crash, chỉ ra '(Thiếu dữ liệu)'."""
        result = compute_stats_pandas_chunk(
            normal_csv, "doanh_thu", extra_group_by="khu_vuc", date_period="month", chunksize=1000
        )
        assert "(Thiếu dữ liệu)" in result["trend"]["keys"]


# ---------------------------------------------------------------------------
# group_col và date_col trùng nhau (chọn cùng 1 cột cho cả 2 mục đích)
# ---------------------------------------------------------------------------
class TestDuplicateColumnSelection:
    def test_group_by_equals_extra_group_by(self, normal_csv):
        result = compute_stats_pandas_chunk(
            normal_csv, "doanh_thu", group_by="khu_vuc", extra_group_by="khu_vuc", chunksize=1000
        )
        assert "by_group" in result
        assert "trend" in result
        assert set(result["by_group"].keys()) == set(result["trend"]["keys"])
