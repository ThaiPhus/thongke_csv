"""
benchmark.py
------------
CHƯƠNG 4 (theo cấu trúc đồ án): Thực nghiệm và đánh giá.

Đo và so sánh:
    - Thời gian chạy (Execution Time)
    - RAM tiêu thụ tối đa (Peak Memory Usage, dùng tracemalloc)

giữa 2 cách cài đặt:
    1. stats_stream.py       (thuần Python, generator + Welford's algorithm)
    2. stats_pandas_chunk.py (Pandas, đọc theo chunksize)

Cách dùng:
    python benchmark.py --file data/doanh_thu.csv --column doanh_thu
"""

import argparse
import time
import tracemalloc
from pathlib import Path

from stats_stream import compute_stats_stream
from stats_pandas_chunk import compute_stats_pandas_chunk


def measure(label: str, func, **kwargs) -> dict:
    tracemalloc.start()
    t0 = time.perf_counter()

    result = func(**kwargs)

    elapsed = time.perf_counter() - t0
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "label": label,
        "elapsed_seconds": round(elapsed, 3),
        "peak_memory_mb": round(peak / (1024 * 1024), 2),
        "result": result,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark: streaming (thuần Python) vs Pandas chunksize")
    parser.add_argument("--file", required=True)
    parser.add_argument("--column", required=True)
    parser.add_argument("--chunksize", type=int, default=200_000)
    args = parser.parse_args()

    if not Path(args.file).exists():
        raise SystemExit(f"Không tìm thấy file: {args.file}")

    file_size_mb = Path(args.file).stat().st_size / (1024 * 1024)
    print(f"File thử nghiệm: {args.file}  (~{file_size_mb:.2f} MB)\n")

    bench_results = []

    print("[1/2] Đang chạy stats_stream (generator + Welford)...")
    bench_results.append(
        measure(
            "stats_stream (Generator/Welford)",
            compute_stats_stream,
            file_path=args.file,
            column=args.column,
            progress_every=0,  # tắt log để không ảnh hưởng benchmark
        )
    )

    print("[2/2] Đang chạy stats_pandas_chunk (Pandas chunksize)...")
    bench_results.append(
        measure(
            "stats_pandas_chunk (Pandas)",
            compute_stats_pandas_chunk,
            file_path=args.file,
            column=args.column,
            chunksize=args.chunksize,
        )
    )

    print("\n" + "=" * 70)
    print(f"{'Phương pháp':35s} | {'Thời gian (s)':>13s} | {'Peak RAM (MB)':>13s}")
    print("-" * 70)
    for b in bench_results:
        print(f"{b['label']:35s} | {b['elapsed_seconds']:>13} | {b['peak_memory_mb']:>13}")
    print("=" * 70)

    # Đối chiếu kết quả để đảm bảo 2 phương pháp cho cùng con số
    o1 = bench_results[0]["result"]["overall"]
    o2 = bench_results[1]["result"]["overall"]
    print("\nĐối chiếu kết quả thống kê (phải khớp nhau):")
    print(f"  mean : stream={o1['mean']:,}   pandas={o2['mean']:,}")
    print(f"  min  : stream={o1['min']:,}   pandas={o2['min']:,}")
    print(f"  max  : stream={o1['max']:,}   pandas={o2['max']:,}")


if __name__ == "__main__":
    main()
