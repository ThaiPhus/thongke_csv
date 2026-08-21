"""
conftest.py
-----------
Fixture dùng chung cho toàn bộ test suite:
    - Thêm thư mục gốc dự án vào sys.path (để `from analytics import ...`
      hoạt động khi chạy `pytest` từ bất kỳ đâu).
    - Sinh các file CSV tổng hợp (synthetic) cho từng tình huống edge-case,
      độc lập với máy/môi trường — không cần file dữ liệu ngoài.
    - Fixture `real_csv_path` trỏ tới bộ dữ liệu thật (Amazon Sale Report)
      nếu người dùng đặt vào tests/data/ hoặc khai báo qua biến môi trường
      AMAZON_CSV_PATH — các test dùng fixture này sẽ tự SKIP (không FAIL)
      nếu không tìm thấy file, để suite vẫn chạy được ở máy không có file đó.
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Cho phép `from analytics import ...`, `from charts import ...` khi chạy
# pytest từ thư mục gốc dự án (thongke_csv/) hoặc từ trong tests/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Bộ dữ liệu THẬT (Amazon Sale Report) — tuỳ chọn, tự skip nếu không có
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def real_csv_path():
    """
    Trả về đường dẫn tới file Amazon_Sale_Report.csv thật nếu có, theo thứ
    tự ưu tiên: biến môi trường AMAZON_CSV_PATH -> tests/data/Amazon_Sale_Report.csv.
    Nếu không tìm thấy, SKIP toàn bộ test dùng fixture này (không FAIL) —
    vì đây là dữ liệu riêng của người dùng, không đi kèm trong repo.
    """
    env_path = os.environ.get("AMAZON_CSV_PATH")
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path(__file__).parent / "data" / "Amazon_Sale_Report.csv")

    for path in candidates:
        if path.exists():
            return str(path)

    pytest.skip(
        "Không tìm thấy file dữ liệu thật. Đặt file vào tests/data/Amazon_Sale_Report.csv "
        "hoặc chạy: AMAZON_CSV_PATH=/duong/dan/file.csv pytest"
    )


# ---------------------------------------------------------------------------
# Dữ liệu tổng hợp (synthetic) — tự sinh, không phụ thuộc file ngoài
# ---------------------------------------------------------------------------
@pytest.fixture()
def csv_dir(tmp_path):
    return tmp_path


@pytest.fixture()
def normal_csv(csv_dir):
    """Dữ liệu bình thường: có nhóm, có ngày, có vài dòng thiếu giá trị."""
    np.random.seed(1)
    n = 5000
    df = pd.DataFrame({
        "ngay": pd.date_range("2024-01-01", periods=n, freq="h").strftime("%Y-%m-%d"),
        "khu_vuc": np.random.choice(["HN", "HCM", "DN"], n),
        "doanh_thu": np.random.uniform(1000, 500_000, n),
    })
    df.loc[df.sample(frac=0.02, random_state=1).index, "doanh_thu"] = np.nan
    path = csv_dir / "normal.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def group_nan_csv(csv_dir):
    """Cột nhóm có giá trị thiếu (None) — để test tổng nhóm phải khớp tổng toàn bộ."""
    np.random.seed(0)
    n = 2000
    df = pd.DataFrame({
        "khu_vuc": np.random.choice(["HN", "HCM", "DN", None], n, p=[0.3, 0.3, 0.3, 0.1]),
        "doanh_thu": np.random.uniform(1000, 500_000, n),
    })
    path = csv_dir / "group_nan.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def same_value_csv(csv_dir):
    """Toàn bộ giá trị cột số giống hệt nhau (min == max) — test histogram/bar degenerate."""
    df = pd.DataFrame({"val": [100] * 500, "grp": ["A"] * 250 + ["B"] * 250})
    path = csv_dir / "same_value.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def single_group_csv(csv_dir):
    """Chỉ có 1 nhóm duy nhất."""
    np.random.seed(2)
    df = pd.DataFrame({"val": np.random.uniform(1, 100, 300), "grp": ["OnlyGroup"] * 300})
    path = csv_dir / "single_group.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def many_groups_csv(csv_dir):
    """20 nhóm — kiểm tra logic gộp 'Khác' (donut) và Top-N (bar)."""
    np.random.seed(3)
    n = 2000
    df = pd.DataFrame({
        "val": np.random.uniform(1, 1000, n),
        "grp": np.random.choice([f"G{i}" for i in range(20)], n),
    })
    path = csv_dir / "many_groups.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def empty_csv(csv_dir):
    """File rỗng hoàn toàn (0 byte)."""
    path = csv_dir / "empty.csv"
    path.write_text("")
    return str(path)


@pytest.fixture()
def only_header_csv(csv_dir):
    """File chỉ có dòng tiêu đề, không có dữ liệu."""
    path = csv_dir / "only_header.csv"
    pd.DataFrame({"val": [], "grp": []}).to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def no_numeric_csv(csv_dir):
    """Không có cột số nào."""
    path = csv_dir / "no_numeric.csv"
    pd.DataFrame({"ten": ["a", "b", "c"], "mo_ta": ["x", "y", "z"]}).to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def all_invalid_csv(csv_dir):
    """Cột giá trị toàn bộ NaN/rỗng."""
    path = csv_dir / "all_invalid.csv"
    pd.DataFrame({"val": [None] * 200, "grp": ["A", "B"] * 100}).to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def dirty_numeric_csv(csv_dir):
    """Cột số lẫn dữ liệu bẩn thực tế: N/A, dấu gạch ngang, chuỗi rỗng, text."""
    df = pd.DataFrame({
        "gia": ["100000", "N/A", "-", "", "250000", "abc", "300000"],
        "loai": ["A", "A", "B", "B", "C", "C", "A"],
    })
    path = csv_dir / "dirty_numeric.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def cp1252_csv(csv_dir):
    """File CSV encoding CP1252 (không phải UTF-8) — mô phỏng file xuất từ Excel Windows."""
    df = pd.DataFrame({
        "ten": ["Café Nord", "Résumé Sud", "Café Est"],
        "gia": [150000, 320000, 890000],
    })
    path = csv_dir / "cp1252.csv"
    df.to_csv(path, index=False, encoding="cp1252")
    return str(path)


@pytest.fixture()
def boolean_csv(csv_dir):
    """Cột kiểu boolean (True/False) làm value_column — test lỗi numpy.bool round()."""
    np.random.seed(4)
    df = pd.DataFrame({
        "is_b2b": np.random.choice([True, False], 500),
        "grp": np.random.choice(["A", "B"], 500),
    })
    path = csv_dir / "boolean.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def numeric_group_csv(csv_dir):
    """Group_by là một cột SỐ (vd mã bưu điện) — test nhãn nhóm phải là string."""
    np.random.seed(5)
    n = 1000
    df = pd.DataFrame({
        "doanh_thu": np.random.uniform(1000, 500_000, n),
        "ma_buu_dien": np.random.choice([100001, 100002, 100003, 700001], n),
    })
    path = csv_dir / "numeric_group.csv"
    df.to_csv(path, index=False)
    return str(path)


@pytest.fixture()
def multi_year_date_csv(csv_dir):
    """Dữ liệu ngày trải qua ranh giới năm (định dạng MM-DD-YY, không phải ISO) —
    test bug sắp xếp xu hướng theo THỜI GIAN THẬT thay vì theo chuỗi alphabet."""
    dates = ["11-15-22", "12-01-22", "12-31-22", "01-01-23", "01-15-23", "02-01-23"]
    df = pd.DataFrame({
        "ngay": dates * 20,
        "doanh_thu": np.random.RandomState(6).uniform(1000, 500_000, len(dates) * 20),
    })
    path = csv_dir / "multi_year.csv"
    df.to_csv(path, index=False)
    return str(path)
