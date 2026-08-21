"""
analytics.py
------------
Lớp phân tích dùng chung cho cả CLI và ứng dụng web (app.py).
Mọi hàm đều đọc file theo `chunksize` (Pandas) để không nạp toàn bộ
file lớn vào RAM cùng lúc — kể cả khi build histogram.

Các hàm chính:
    - detect_encoding(...)                  : tự dò encoding file (UTF-8/Latin-1/CP1252...)
    - compute_overall_and_group_stats(...)  : wrapper quanh stats_pandas_chunk.py
    - compute_histogram(...)                : histogram 2-pass, streaming
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from stats_pandas_chunk import compute_stats_pandas_chunk

COMMON_ENCODINGS = ["utf-8", "utf-8-sig", "latin1", "cp1252"]


def detect_encoding(file_path: str) -> str:
    """
    Thử đọc vài dòng đầu của file bằng các encoding phổ biến, trả về
    encoding đầu tiên đọc thành công. Giúp chương trình không bị lỗi
    UnicodeDecodeError khi người dùng upload file CSV xuất từ Excel/hệ
    thống khác (thường dùng cp1252/latin1 thay vì utf-8).
    """
    for enc in COMMON_ENCODINGS:
        try:
            pd.read_csv(file_path, nrows=5, encoding=enc)
            return enc
        except UnicodeDecodeError:
            continue
        except Exception:
            # Lỗi khác không liên quan encoding (vd: file rỗng) -> vẫn trả về utf-8
            return enc
    return "utf-8"  # fallback cuối cùng


def compute_overall_and_group_stats(
    file_path: str,
    column: str,
    group_by: Optional[str] = None,
    extra_group_by: Optional[str] = None,
    date_period: Optional[str] = None,
    chunksize: int = 200_000,
    encoding: str = "utf-8",
) -> dict:
    """
    Wrapper mỏng quanh stats_pandas_chunk để dùng chung trong app.py.
    `extra_group_by` (vd: cột ngày) được tính GỘP trong cùng lượt đọc này
    (không phải đọc file thêm một lần riêng) để giảm số lượt quét file lớn.
    `date_period` ("day"/"week"/"month"/"quarter"/"year"): nếu có, gộp
    `extra_group_by` theo kỳ báo cáo tương ứng thay vì theo đúng giá trị
    thô trong file — xem stats_pandas_chunk.DATE_PERIODS.
    """
    return compute_stats_pandas_chunk(
        file_path, column, chunksize=chunksize, group_by=group_by,
        extra_group_by=extra_group_by, date_period=date_period, encoding=encoding,
    )


def compute_histogram(
    file_path: str,
    column: str,
    bins: int = 30,
    value_min: Optional[float] = None,
    value_max: Optional[float] = None,
    chunksize: int = 200_000,
    encoding: str = "utf-8",
) -> dict:
    """
    Tính histogram cho một cột số bằng phương pháp streaming 2 lượt đọc:
      - Nếu chưa biết min/max, quét 1 lượt để lấy min/max (đọc theo chunk).
      - Lượt 2: với các cạnh bin (bin edges) cố định, mỗi chunk tự tính
        np.histogram cục bộ rồi cộng dồn vào mảng đếm chung.
    Nhờ đó không cần giữ toàn bộ cột dữ liệu trong RAM để vẽ histogram,
    kể cả khi file có hàng chục triệu dòng.

    QUAN TRỌNG: `value_min`/`value_max` truyền vào thường lấy từ kết quả
    thống kê tổng quan (vd overall["min"]/overall["max"]), vốn đã bị làm
    tròn 2 chữ số thập phân — có thể LỆCH so với giá trị thật trong file
    (vd giá trị thật 1048.3783... bị làm tròn thành 1048.38, tức là LỚN
    HƠN giá trị thật). Nếu không xử lý, np.histogram() sẽ ÂM THẦM LOẠI BỎ
    những giá trị nằm ngoài khoảng [value_min, value_max] do lệch làm tròn
    này, khiến tổng số đếm của histogram không khớp tổng số dòng hợp lệ.
    Do đó luôn "kẹp" (clip) dữ liệu vào đúng khoảng trước khi đếm bin.
    """
    if value_min is None or value_max is None:
        vmin, vmax = math.inf, -math.inf
        for chunk in pd.read_csv(file_path, usecols=[column], chunksize=chunksize, encoding=encoding):
            vals = pd.to_numeric(chunk[column], errors="coerce").astype("float64").dropna()
            if len(vals):
                vmin = min(vmin, vals.min())
                vmax = max(vmax, vals.max())
        value_min, value_max = vmin, vmax

    edges = np.linspace(value_min, value_max, bins + 1)
    counts = np.zeros(bins, dtype=np.int64)

    for chunk in pd.read_csv(file_path, usecols=[column], chunksize=chunksize, encoding=encoding):
        vals = pd.to_numeric(chunk[column], errors="coerce").astype("float64").dropna().to_numpy()
        if len(vals):
            vals = np.clip(vals, value_min, value_max)
            c, _ = np.histogram(vals, bins=edges)
            counts += c

    return {"edges": edges.tolist(), "counts": counts.tolist()}
