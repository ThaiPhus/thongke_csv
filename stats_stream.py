"""
stats_stream.py
----------------
CHƯƠNG 3 (theo cấu trúc đồ án): Cài đặt chương trình - hướng tối ưu bộ nhớ.

Đọc file CSV rất lớn (doanh thu theo ngày) và tính min / max / trung bình /
độ lệch chuẩn cho một cột số, KHÔNG nạp toàn bộ file vào RAM.

Kỹ thuật sử dụng:
    - Generator/Iterator: đọc file theo từng dòng bằng csv.DictReader,
      thay vì .read() hay list toàn bộ dữ liệu.
    - Thuật toán Welford's online algorithm: tính mean/variance "trực
      tuyến" (online), độ phức tạp O(1) bộ nhớ, O(n) thời gian, ổn định
      về số học hơn cách cộng dồn tổng bình phương thông thường.

Cách dùng (CLI):
    python stats_stream.py --file data/doanh_thu.csv --column doanh_thu

Cách dùng (import làm module, ví dụ ghép vào pipeline khác):
    from stats_stream import compute_stats_stream
    result = compute_stats_stream("data/doanh_thu.csv", "doanh_thu")
"""

import argparse
import csv
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional


@dataclass
class RunningStats:
    """Giữ trạng thái thống kê 'trực tuyến' cho một cột số (thuật toán Welford)."""

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0  # tổng bình phương sai khác lũy kế (Welford)
    min_value: float = field(default=math.inf)
    max_value: float = field(default=-math.inf)
    total: float = 0.0
    invalid_count: int = 0  # số dòng có giá trị rỗng / không parse được

    def update(self, x: float) -> None:
        self.count += 1
        self.total += x
        delta = x - self.mean
        self.mean += delta / self.count
        delta2 = x - self.mean
        self.m2 += delta * delta2
        if x < self.min_value:
            self.min_value = x
        if x > self.max_value:
            self.max_value = x

    @property
    def variance(self) -> float:
        return self.m2 / self.count if self.count > 1 else 0.0

    @property
    def stddev(self) -> float:
        return math.sqrt(self.variance)

    def to_dict(self) -> dict:
        return {
            "count_valid": self.count,
            "count_invalid": self.invalid_count,
            "sum": round(self.total, 2),
            "mean": round(self.mean, 2),
            "min": round(self.min_value, 2) if self.count else None,
            "max": round(self.max_value, 2) if self.count else None,
            "stddev": round(self.stddev, 2),
        }


def _iter_csv_rows(file_path: str) -> Iterator[dict]:
    """Generator đọc file CSV theo từng dòng (không load cả file vào RAM)."""
    with open(file_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def compute_stats_stream(
    file_path: str,
    column: str,
    group_by: Optional[str] = None,
    progress_every: int = 1_000_000,
) -> dict:
    """
    Tính thống kê (count, sum, mean, min, max, stddev) cho `column`.
    Nếu `group_by` được cung cấp, kết quả được tách theo từng nhóm
    (ví dụ: thống kê doanh thu theo từng khu_vuc).

    Trả về dict:
        {"overall": RunningStats.to_dict(), "by_group": {key: {...}, ...}}
    """
    overall = RunningStats()
    groups: dict[str, RunningStats] = {}

    t0 = time.perf_counter()
    n_rows = 0

    for row in _iter_csv_rows(file_path):
        n_rows += 1
        raw = row.get(column, "")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            overall.invalid_count += 1
            if group_by:
                key = row.get(group_by, "N/A")
                groups.setdefault(key, RunningStats())
                groups[key].invalid_count += 1
            continue

        overall.update(value)

        if group_by:
            key = row.get(group_by, "N/A")
            groups.setdefault(key, RunningStats())
            groups[key].update(value)

        if progress_every and n_rows % progress_every == 0:
            print(f"  ... đã xử lý {n_rows:,} dòng")

    elapsed = time.perf_counter() - t0

    result = {
        "file": file_path,
        "column": column,
        "rows_read": n_rows,
        "elapsed_seconds": round(elapsed, 3),
        "overall": overall.to_dict(),
    }
    if group_by:
        result["group_by"] = group_by
        result["by_group"] = {k: v.to_dict() for k, v in sorted(groups.items())}
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
                  f"  max={stats['max']:>14,.2f}  count={stats['count_valid']:,}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Thống kê streaming từ file CSV lớn (min/max/mean/stddev)")
    parser.add_argument("--file", required=True, help="Đường dẫn file CSV")
    parser.add_argument("--column", required=True, help="Tên cột số cần thống kê (vd: doanh_thu)")
    parser.add_argument("--group-by", default=None, help="Tên cột dùng để nhóm (vd: khu_vuc)")
    args = parser.parse_args()

    if not Path(args.file).exists():
        raise SystemExit(f"Không tìm thấy file: {args.file}")

    result = compute_stats_stream(args.file, args.column, group_by=args.group_by)
    print_report(result)


if __name__ == "__main__":
    main()
