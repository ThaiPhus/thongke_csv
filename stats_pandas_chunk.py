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


DATE_PERIODS = ("day", "week", "month", "quarter", "year")

# Vài định dạng ngày phổ biến hay gặp trong file CSV xuất từ Excel/hệ thống
# khác (không theo chuẩn ISO). Dò 1 LẦN DUY NHẤT trên một mẫu nhỏ trước khi
# đọc file theo chunk, thay vì để pandas tự suy luận lại (chậm, phải fallback
# sang dateutil từng phần tử) ở MỖI chunk.
_COMMON_DATE_FORMATS = [
    "%m-%d-%y", "%d-%m-%y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y",
    "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y", "%d.%m.%Y", "%Y-%m-%d %H:%M:%S",
]


def _detect_date_format(file_path: str, column: str, encoding: str, sample_size: int = 500) -> str | None:
    """
    Đọc thử một mẫu nhỏ của cột ngày để dò ra định dạng cụ thể (vd "%m-%d-%y").
    Nếu tìm được, việc parse ngày cho toàn bộ file sẽ dùng C-parser nhanh của
    pandas thay vì phải fallback từng phần tử qua dateutil (chậm hơn nhiều
    lần và in cảnh báo liên tục cho mỗi chunk).
    Trả về None nếu không dò được định dạng nào đạt độ chính xác > 95% —
    khi đó vẫn hoạt động bình thường, chỉ là chậm hơn (pandas tự suy luận).
    """
    try:
        sample = pd.read_csv(file_path, usecols=[column], nrows=sample_size, encoding=encoding)[column].dropna()
    except Exception:
        return None
    if sample.empty:
        return None
    for fmt in _COMMON_DATE_FORMATS:
        try:
            parsed = pd.to_datetime(sample, format=fmt, errors="coerce")
        except (ValueError, TypeError):
            continue
        if parsed.notna().mean() > 0.95:
            return fmt
    return None


def _bucket_date_series(series: pd.Series, period: str, date_format: str | None = None) -> pd.Series:
    """
    Chuyển cột ngày về nhãn theo KỲ BÁO CÁO (ngày/tuần/tháng/quý/năm).

    QUAN TRỌNG: luôn parse về datetime thật (pd.to_datetime) rồi format lại
    theo chuẩn ISO (YYYY-MM-DD, YYYY-Wxx, YYYY-MM, YYYY-Qx, YYYY) — KHÔNG
    dùng trực tiếp chuỗi ngày gốc trong file. Lý do: nếu giữ nguyên chuỗi
    gốc (vd "04-30-22" kiểu MM-DD-YY) rồi sort_index() theo alphabet, thứ tự
    sẽ SAI khi dữ liệu trải qua nhiều năm (vd "01-01-23" bị sắp xếp trước
    "12-31-22" vì so sánh chuỗi, dù về mặt thời gian nó ở SAU). Định dạng
    ISO luôn sắp đúng thứ tự thời gian khi sort dạng chuỗi.

    `date_format`: định dạng đã dò được từ _detect_date_format (nếu có) để
    parse nhanh bằng C-parser thay vì fallback chậm qua dateutil.

    Ngày không parse được (NaT) sẽ được giữ nguyên là NaN/NA để _to_group_label
    gán nhãn "(Thiếu dữ liệu)" ở bước sau — không tự bịa ra một "kỳ" giả.
    """
    if date_format:
        dt = pd.to_datetime(series, format=date_format, errors="coerce")
    else:
        dt = pd.to_datetime(series, errors="coerce")

    if period == "day":
        return dt.dt.strftime("%Y-%m-%d")
    if period == "month":
        return dt.dt.strftime("%Y-%m")
    if period == "year":
        return dt.dt.strftime("%Y")
    if period == "quarter":
        # Dùng dtype "string" (nullable) để NA lan truyền đúng khi nối chuỗi,
        # tránh bị biến thành chuỗi "nan-Q<NA>" xấu xí.
        year_s = dt.dt.year.astype("Int64").astype("string")
        q_s = dt.dt.quarter.astype("Int64").astype("string")
        return year_s + "-Q" + q_s
    if period == "week":
        iso = dt.dt.isocalendar()
        year_s = iso["year"].astype("Int64").astype("string")
        week_s = iso["week"].astype("Int64").astype("string").str.zfill(2)
        return year_s + "-W" + week_s

    raise ValueError(f"Kỳ báo cáo không hỗ trợ: {period!r} (chỉ nhận {DATE_PERIODS})")


def compute_stats_pandas_chunk(
    file_path: str,
    column: str,
    chunksize: int = 200_000,
    group_by: str | None = None,
    extra_group_by: str | None = None,
    date_period: str | None = None,
    encoding: str = "utf-8",
) -> dict:
    """
    Tính thống kê tổng quan (+ theo nhóm, + theo `extra_group_by` nếu có,
    ví dụ cột ngày để làm xu hướng) trong CÙNG MỘT lượt đọc file.

    `date_period`: nếu có (một trong DATE_PERIODS), cột `extra_group_by`
    được coi là cột NGÀY và sẽ được gộp theo kỳ báo cáo tương ứng (ngày/
    tuần/tháng/quý/năm) thay vì nhóm theo đúng giá trị thô trong file.

    Quan trọng: chỉ đọc đúng các cột cần dùng (`usecols`) — với file có
    nhiều cột thừa (vài chục cột), điều này giảm đáng kể thời gian parse
    và tránh các cảnh báo/độ trễ do suy luận kiểu dữ liệu (dtype inference)
    trên các cột không liên quan.
    """
    if date_period is not None and date_period not in DATE_PERIODS:
        raise ValueError(f"date_period phải là một trong {DATE_PERIODS}, nhận: {date_period!r}")

    # Dò định dạng ngày MỘT LẦN trước khi đọc file theo chunk (xem docstring
    # _detect_date_format) — tránh phải suy luận lại (chậm) ở mỗi chunk.
    date_format = None
    if date_period and extra_group_by:
        date_format = _detect_date_format(file_path, extra_group_by, encoding)

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
                if date_period:
                    ecol_raw = _bucket_date_series(valid_chunk[extra_group_by], date_period, date_format)
                else:
                    ecol_raw = valid_chunk[extra_group_by]
                ecol = ecol_raw.map(_to_group_label)
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
    if "trend" in result:
        print("-" * 60)
        print(f"Xu hướng theo '{result['extra_group_by']}':")
        for k, s, c in zip(result["trend"]["keys"], result["trend"]["sum"], result["trend"]["count"]):
            print(f"  - {k:12s}: sum={s:>14,.2f}  count={c:,}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Thống kê CSV lớn bằng Pandas (chunksize)")
    parser.add_argument("--file", required=True)
    parser.add_argument("--column", required=True)
    parser.add_argument("--group-by", default=None)
    parser.add_argument("--date-column", default=None, help="Cột ngày để xem xu hướng (tuỳ chọn)")
    parser.add_argument("--date-period", default=None, choices=DATE_PERIODS,
                         help="Gộp cột --date-column theo kỳ báo cáo: day/week/month/quarter/year")
    parser.add_argument("--chunksize", type=int, default=200_000)
    args = parser.parse_args()

    if not Path(args.file).exists():
        raise SystemExit(f"Không tìm thấy file: {args.file}")

    result = compute_stats_pandas_chunk(
        args.file, args.column, chunksize=args.chunksize, group_by=args.group_by,
        extra_group_by=args.date_column, date_period=args.date_period,
    )
    print_report(result)


if __name__ == "__main__":
    main()
