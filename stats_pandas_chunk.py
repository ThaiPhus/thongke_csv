"""
stats_pandas_chunk.py
----------------------
Phiên bản dùng Pandas với chunksize (đọc theo lô/batch, không đọc từng dòng
như csv thuần) để so sánh hiệu năng và làm bước đệm hướng tới PySpark.

Ý tưởng giống mô hình MapReduce đơn giản:
    - Map : mỗi chunk (lô dữ liệu) được tính thống kê cục bộ (sum, count, min, max)
    - Reduce: các thống kê cục bộ được gộp lại (combine) thành kết quả toàn cục

Cách dùng:
    python stats_pandas_chunk.py --file data/doanh_thu.csv --column doanh_thu --chunksize 200000
"""

import argparse
import math
import time
from pathlib import Path

import pandas as pd


def _to_group_label(val) -> str:
    """
    Chuẩn hoá giá trị cột nhóm thành CHUỖI — bắt buộc, vì charts.py giả định
    nhãn nhóm luôn là str (so sánh với "Khác", cắt chuỗi rút gọn nhãn dài...).
    Nếu group_by là một cột SỐ (vd mã bưu điện), giá trị đọc về có thể là
    float (400001.0) — bỏ đuôi ".0" cho gọn thay vì hiện nguyên "400001.0".
    """
    if pd.isna(val):
        return "(Thiếu dữ liệu)"
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


def compute_stats_pandas_chunk(
    file_path: str,
    column: str,
    chunksize: int = 200_000,
    group_by: str | None = None,
    extra_group_by: str | None = None,
    encoding: str = "utf-8",
) -> dict:
    """
    Tính thống kê tổng quan (+ theo nhóm, + theo `extra_group_by` nếu có,
    ví dụ cột ngày để làm xu hướng) trong CÙNG MỘT lượt đọc file.

    Quan trọng: chỉ đọc đúng các cột cần dùng (`usecols`) — với file có
    nhiều cột thừa (vài chục cột), điều này giảm đáng kể thời gian parse
    và tránh các cảnh báo/độ trễ do suy luận kiểu dữ liệu (dtype inference)
    trên các cột không liên quan.
    """
    total_count = 0
    total_sum = 0.0
    total_sumsq = 0.0
    global_min = math.inf
    global_max = -math.inf
    invalid_count = 0
    n_rows = 0

    group_frames = []
    trend_frames = []

    needed_cols = [column]
    if group_by:
        needed_cols.append(group_by)
    if extra_group_by and extra_group_by not in needed_cols:
        needed_cols.append(extra_group_by)

    t0 = time.perf_counter()

    reader = pd.read_csv(file_path, usecols=needed_cols, chunksize=chunksize, low_memory=False, encoding=encoding)
    for chunk in reader:
        n_rows += len(chunk)
        # QUAN TRỌNG: pandas coi cột kiểu bool (True/False) là "đã là số" nên
        # pd.to_numeric() để nguyên dtype bool, không ép kiểu — dẫn tới lỗi
        # "numpy.bool doesn't define __round__" khi tính toán thống kê phía
        # sau. Ép rõ về float64 để luôn là số thực sự.
        numeric = pd.to_numeric(chunk[column], errors="coerce").astype("float64")
        invalid_count += int(numeric.isna().sum())
        valid = numeric.dropna()

        # --- MAP: thống kê cục bộ trên chunk ---
        c_count = len(valid)
        if c_count:
            total_count += c_count
            total_sum += valid.sum()
            total_sumsq += (valid ** 2).sum()
            global_min = min(global_min, valid.min())
            global_max = max(global_max, valid.max())

        if group_by or extra_group_by:
            chunk = chunk.copy()
            chunk[column] = numeric
            valid_chunk = chunk.dropna(subset=[column])

            # QUAN TRỌNG: pandas groupby() mặc định BỎ QUA các dòng có giá trị
            # NaN/thiếu ở cột nhóm — nếu không xử lý, các dòng đó "biến mất"
            # khỏi bảng theo nhóm dù vẫn được tính trong thống kê tổng quan,
            # khiến tổng các nhóm cộng lại không khớp với tổng toàn bộ.
            # Gán nhãn rõ ràng "(Thiếu dữ liệu)" để giữ lại và người dùng biết.
            if group_by:
                gcol = valid_chunk[group_by].map(_to_group_label)
                group_frames.append(
                    valid_chunk.groupby(gcol)[column].agg(["count", "sum", "min", "max"])
                )
            if extra_group_by:
                ecol = valid_chunk[extra_group_by].map(_to_group_label)
                trend_frames.append(
                    valid_chunk.groupby(ecol)[column].agg(["count", "sum"])
                )

    elapsed = time.perf_counter() - t0

    mean = total_sum / total_count if total_count else 0.0
    # var(X) = E[X^2] - (E[X])^2, tính từ tổng lũy kế theo từng chunk (kiểu MapReduce)
    variance = (total_sumsq / total_count - mean ** 2) if total_count else 0.0
    stddev = math.sqrt(max(variance, 0.0))

    result = {
        "file": file_path,
        "column": column,
        "rows_read": n_rows,
        "elapsed_seconds": round(elapsed, 3),
        "overall": {
            "count_valid": total_count,
            "count_invalid": invalid_count,
            "sum": round(total_sum, 2),
            "mean": round(mean, 2),
            "min": round(global_min, 2) if total_count else None,
            "max": round(global_max, 2) if total_count else None,
            "stddev": round(stddev, 2),
        },
    }

    # --- REDUCE: gộp thống kê nhóm từ các chunk ---
    if group_by and group_frames:
        combined = pd.concat(group_frames)
        agg = combined.groupby(level=0).apply(
            lambda df: pd.Series({
                "count_valid": int(df["count"].sum()),  # ép kiểu int rõ ràng, tránh hiển thị "150.0"
                "min": df["min"].min(),
                "max": df["max"].max(),
                "mean": df["sum"].sum() / df["count"].sum(),
            })
        )
        result["group_by"] = group_by
        by_group = agg.round(2).to_dict(orient="index")
        for stats in by_group.values():
            stats["count_valid"] = int(stats["count_valid"])  # .round(2) ở trên có thể trả lại float
        result["by_group"] = by_group

    # --- REDUCE: gộp xu hướng theo cột phụ (vd: ngày) từ các chunk ---
    if extra_group_by and trend_frames:
        combined_trend = pd.concat(trend_frames).groupby(level=0).sum()
        combined_trend = combined_trend.sort_index()
        result["extra_group_by"] = extra_group_by
        result["trend"] = {
            "keys": [str(k) for k in combined_trend.index.tolist()],
            "sum": [round(float(v), 2) for v in combined_trend["sum"].tolist()],
            "count": [int(v) for v in combined_trend["count"].tolist()],
        }

    return result


def print_report(result: dict) -> None:
    print("=" * 60)
    print(f"File          : {result['file']}")
    print(f"Cột thống kê  : {result['column']}")
    print(f"Số dòng đọc   : {result['rows_read']:,}")
    print(f"Thời gian xử lý: {result['elapsed_seconds']} giây")
    print("-" * 60)
    o = result["overall"]
    print(f"Số dòng hợp lệ : {o['count_valid']:,}  | Dòng lỗi/thiếu: {o['count_invalid']:,}")
    print(f"Tổng (sum)     : {o['sum']:,}")
    print(f"Trung bình     : {o['mean']:,}")
    print(f"Nhỏ nhất (min) : {o['min']:,}")
    print(f"Lớn nhất (max) : {o['max']:,}")
    print(f"Độ lệch chuẩn  : {o['stddev']:,}")
    if "by_group" in result:
        print("-" * 60)
        print(f"Thống kê theo '{result['group_by']}':")
        for key, stats in result["by_group"].items():
            print(f"  - {key:12s}: mean={stats['mean']:>14,.2f}  min={stats['min']:>14,.2f}"
                  f"  max={stats['max']:>14,.2f}  count={int(stats['count_valid']):,}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Thống kê CSV lớn bằng Pandas (chunksize)")
    parser.add_argument("--file", required=True)
    parser.add_argument("--column", required=True)
    parser.add_argument("--group-by", default=None)
    parser.add_argument("--chunksize", type=int, default=200_000)
    args = parser.parse_args()

    if not Path(args.file).exists():
        raise SystemExit(f"Không tìm thấy file: {args.file}")

    result = compute_stats_pandas_chunk(
        args.file, args.column, chunksize=args.chunksize, group_by=args.group_by
    )
    print_report(result)


if __name__ == "__main__":
    main()
