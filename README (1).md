# tests/data/

Đặt file `Amazon_Sale_Report.csv` (hoặc bộ dữ liệu thật khác của bạn) vào
thư mục này để chạy được nhóm test tích hợp trong `tests/test_real_dataset.py`.

File CSV KHÔNG được commit lên Git (đã có trong `.gitignore` qua rule `*.csv`)
vì đây là dữ liệu riêng, không nên đưa vào kho mã nguồn dùng chung.

Cách khác: khai báo đường dẫn qua biến môi trường thay vì copy file vào đây:

```bash
AMAZON_CSV_PATH=/duong/dan/toi/Amazon_Sale_Report.csv pytest tests/test_real_dataset.py -v
```

Nếu không có file, các test trong `test_real_dataset.py` sẽ tự **SKIP**
(không FAIL) — toàn bộ các test khác trong `tests/` vẫn chạy bình thường
vì chúng dùng dữ liệu tổng hợp (synthetic) tự sinh, không phụ thuộc file này.
