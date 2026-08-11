"""
generate_data.py
-----------------
Sinh dữ liệu CSV mẫu mô phỏng "doanh thu theo ngày" của nhiều chi nhánh,
dùng để thử nghiệm chương trình thống kê với file có kích thước lớn.

Cách dùng:
    python generate_data.py --rows 5000000 --out data/doanh_thu.csv

Ghi chú tối ưu bộ nhớ:
    Dữ liệu được ghi trực tiếp ra file theo từng dòng (writer.writerow),
    KHÔNG build toàn bộ dữ liệu trong một list rồi mới ghi, để RAM luôn
    ở mức ổn định dù --rows tăng lên hàng chục triệu dòng.
"""

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

REGIONS = ["Ha Noi", "TP HCM", "Da Nang", "Can Tho", "Hai Phong"]
PRODUCTS = ["SP_A", "SP_B", "SP_C", "SP_D", "SP_E", "SP_F"]


def generate(rows: int, out_path: str, start_date: date, seed: int = 42) -> None:
    random.seed(seed)
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["ngay", "khu_vuc", "san_pham", "doanh_thu", "so_luong"])

        current_date = start_date
        for i in range(rows):
            # Mỗi ~2000 dòng thì tăng ngày lên 1, mô phỏng dữ liệu nhiều ngày
            if i % 2000 == 0 and i != 0:
                current_date += timedelta(days=1)

            khu_vuc = random.choice(REGIONS)
            san_pham = random.choice(PRODUCTS)
            so_luong = random.randint(1, 50)
            don_gia = random.uniform(50_000, 2_000_000)
            doanh_thu = round(so_luong * don_gia, 0)

            # ~0.5% dữ liệu "bẩn" để chương trình thống kê phải xử lý được
            if random.random() < 0.005:
                doanh_thu = ""  # giá trị thiếu

            writer.writerow([current_date.isoformat(), khu_vuc, san_pham, doanh_thu, so_luong])

            if (i + 1) % 500_000 == 0:
                print(f"  ... đã sinh {i + 1:,} dòng")

    print(f"Hoàn tất: {rows:,} dòng -> {out_file.resolve()}")
    print(f"Kích thước file: {out_file.stat().st_size / (1024*1024):.2f} MB")


def main():
    parser = argparse.ArgumentParser(description="Sinh dữ liệu CSV mẫu doanh thu")
    parser.add_argument("--rows", type=int, default=1_000_000, help="Số dòng dữ liệu")
    parser.add_argument("--out", type=str, default="data/doanh_thu.csv", help="Đường dẫn file output")
    parser.add_argument("--start-date", type=str, default="2025-01-01", help="Ngày bắt đầu (YYYY-MM-DD)")
    args = parser.parse_args()

    y, m, d = map(int, args.start_date.split("-"))
    generate(args.rows, args.out, date(y, m, d))


if __name__ == "__main__":
    main()
