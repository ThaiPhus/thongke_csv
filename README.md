# Đề tài 2: Tính toán thống kê từ file CSV lớn (doanh thu theo ngày)

Chương trình đọc file CSV **doanh thu theo ngày** có kích thước lớn và tính
**tổng, trung bình, min, max, độ lệch chuẩn**, tối ưu để không tràn RAM —
bám theo "CẤU TRÚC ĐỒ ÁN MÔN HỌC" (tối ưu bộ nhớ, Streaming/Generator,
hướng mở rộng lên Pandas/Spark). Có giao diện web cho phép **chọn file từ
máy tính**, **trực quan hoá** và **xuất báo cáo HTML**.

## Cấu trúc thư mục

```
thongke_csv/
├── app.py                  # ⭐ Ứng dụng WEB (Streamlit): upload file, dashboard, xuất HTML
├── analytics.py            # Hàm phân tích dùng chung: dò encoding, histogram streaming
├── charts.py                # Vẽ biểu đồ (bar/donut/histogram/line) -> ảnh base64
├── report_generator.py     # Sinh file báo cáo HTML tự chứa (nhúng sẵn biểu đồ)
├── tokens.css               # Hệ token thiết kế (màu/font/spacing) — bản portable, đối chiếu
├── generate_data.py        # Sinh dữ liệu CSV mẫu (doanh thu theo ngày) để thử nghiệm
├── stats_stream.py         # CLI cách 1: thuần Python, Generator + Welford's algorithm (RAM thấp)
├── stats_pandas_chunk.py   # CLI cách 2 + lõi tính toán của web app: Pandas + chunksize
├── benchmark.py            # Đo & so sánh thời gian / RAM giữa 2 cách CLI
├── requirements.txt        # Thư viện cần cài
└── .streamlit/config.toml  # Giới hạn upload, theme màu cho Streamlit
```

## Cách chạy

### A. Ứng dụng web (khuyến nghị — có upload file, dashboard, xuất HTML)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Trình duyệt sẽ tự mở tại `http://localhost:8501`. Các bước sử dụng (ở sidebar):
1. Chọn file CSV từ máy tính (tự động dò encoding UTF-8/Latin-1/CP1252).
2. Chọn cột số cần thống kê, cột để nhóm (vd: `khu_vuc`), cột thời gian (vd: `ngay`).
3. Bấm **"Chạy phân tích"** → xem 3 tab: Thống kê tổng quan / Biểu đồ trực quan / Xuất báo cáo.
4. Ở tab "Xuất báo cáo", bấm **"Tải báo cáo HTML"** để tải file hoàn chỉnh (đính kèm được vào Phụ lục đồ án).

### B. Chạy dòng lệnh (CLI) — dùng khi muốn benchmark hiệu năng thuần

```bash
# 1. Sinh dữ liệu mẫu (ví dụ 5 triệu dòng, ~180MB)
python generate_data.py --rows 5000000 --out data/doanh_thu.csv

# 2. Thống kê bằng cách streaming (RAM thấp)
python stats_stream.py --file data/doanh_thu.csv --column doanh_thu --group-by khu_vuc

# 3. Thống kê bằng Pandas chunksize (nhanh hơn)
python stats_pandas_chunk.py --file data/doanh_thu.csv --column doanh_thu --group-by khu_vuc

# 4. So sánh hiệu năng 2 cách (thời gian + RAM đỉnh)
python benchmark.py --file data/doanh_thu.csv --column doanh_thu
```

## Ánh xạ vào các Chương của đồ án

**Chương 1 – Cơ sở lý thuyết**
- 1.2 Kiến thức liên quan: khái niệm thống kê mô tả (mean/min/max/stddev),
  Generator/Iterator trong Python.
- 1.4 Công nghệ sử dụng: Python, Pandas, Streamlit (giao diện web),
  Matplotlib (trực quan hoá), NumPy (histogram).

**Chương 2 – Phân tích bài toán**
- 2.2 Phân tích dữ liệu: cột `doanh_thu` (số), dữ liệu mẫu có sẵn phần
  giá trị thiếu để mô phỏng dữ liệu thực tế cần làm sạch (Veracity).

**Chương 3 – Xây dựng chương trình**
- 3.1 Môi trường: Python 3, Pandas, Streamlit, Matplotlib, NumPy.
- 3.3 Thuật toán:
  - **Welford's online algorithm** (`stats_stream.py`) — tính mean/variance
    theo từng dòng, độ phức tạp O(1) bộ nhớ, không cần giữ toàn bộ dữ liệu
    để tính lại tổng bình phương (tránh sai số/tràn số so với công thức thô).
  - **Histogram streaming 2 lượt đọc** (`analytics.py`) — lượt 1 lấy min/max,
    lượt 2 cộng dồn `np.histogram` từng chunk, không cần giữ toàn bộ cột
    dữ liệu trong RAM để vẽ biểu đồ phân phối.
- 3.4 Cài đặt:
  - `stats_stream.py` (generator, thuần Python) so với `stats_pandas_chunk.py`
    (kiểu Map–Reduce: mỗi chunk tính cục bộ rồi gộp lại) — cả hai đều chỉ
    đọc đúng cột cần dùng (`usecols`) để tránh phải parse các cột thừa.
  - `app.py` là giao diện web: chọn file CSV từ máy tính, cấu hình cột phân
    tích, xem dashboard 4 biểu đồ (cột, donut, histogram, đường xu hướng —
    module `charts.py`) kèm insight tự động rút ra từ số liệu, và xuất báo
    cáo HTML tự chứa (module `report_generator.py`, biểu đồ nhúng base64
    nên không phụ thuộc file ngoài khi mở lại).

**Chương 4 – Thực nghiệm và đánh giá**
- Dùng `generate_data.py` để tạo file 100MB / 500MB / 1GB.
- Dùng `benchmark.py` để đo Execution Time và Peak Memory Usage
  (bằng `tracemalloc`), lập bảng/biểu đồ so sánh hai cách cài đặt.
- Nhận xét: streaming tối ưu RAM tuyệt đối nhưng chậm hơn do xử lý từng
  dòng bằng Python thuần; Pandas vector hoá nên nhanh hơn đáng kể nhưng
  RAM tăng theo kích thước mỗi chunk.

**Hướng phát triển**: chuyển `stats_pandas_chunk.py` sang PySpark
(`df.groupBy().agg()`) để chạy phân tán trên cluster khi dữ liệu lên
hàng chục/hàng trăm GB — đúng hướng đã nêu trong file cấu trúc đồ án.

## Ghi chú xử lý dữ liệu bẩn

Chương trình tự động bỏ qua (và đếm số lượng) các dòng có giá trị rỗng/không
parse được ở cột thống kê, thay vì làm crash — tương ứng với đặc trưng
**Veracity** đã nêu trong slide "Tổng quan về Big Data". Với cột dùng để
nhóm, các dòng thiếu giá trị được gán nhãn rõ ràng "(Thiếu dữ liệu)" thay vì
bị âm thầm loại bỏ, để tổng các nhóm luôn khớp với tổng toàn bộ.

## 🚀 Đưa ứng dụng lên hosting (deploy)

### Cách 1: Streamlit Community Cloud (miễn phí, khuyến nghị cho đồ án)

**Bước 1 — Đưa code lên GitHub**
```bash
cd thongke_csv
git init
git add .
git commit -m "Đồ án: chương trình thống kê CSV"
git branch -M main
git remote add origin https://github.com/<ten-github>/<ten-repo>.git
git push -u origin main
```
Lưu ý: giữ nguyên cấu trúc thư mục `.streamlit/config.toml` (không đặt
`config.toml` ở gốc repo) — nếu không Streamlit sẽ không áp dụng cấu hình.

**Bước 2 — Deploy**
1. Vào **https://share.streamlit.io** → đăng nhập bằng tài khoản GitHub.
2. Bấm **"New app"** → chọn repo vừa đẩy lên.
3. Điền Branch: `main`, Main file path: `app.py`.
4. Bấm **Deploy**. Sau khoảng 1–2 phút sẽ có link dạng
   `https://<ten-app>.streamlit.app` để chia sẻ/nộp kèm đồ án.

Mỗi khi `git push` code mới, app sẽ tự động build lại.

**Giới hạn cần biết:** gói miễn phí thường 1 CPU/~1GB RAM; app sẽ "ngủ" nếu
không có người dùng trong một thời gian — chỉ cần mở lại link là tự khởi động.

### Cách 2: Hugging Face Spaces (miễn phí)

Tạo Space mới tại **https://huggingface.co/new-space**, chọn SDK = **Streamlit**,
rồi upload toàn bộ file trong `thongke_csv/` (kể cả `requirements.txt`).

### Cách 3: Render.com (miễn phí có giới hạn)

Đẩy code lên GitHub như Cách 1, tạo **New Web Service** trên render.com, cấu hình:
- Build Command: `pip install -r requirements.txt`
- Start Command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

> Cách 1 (Streamlit Community Cloud) là đơn giản và miễn phí hoàn toàn nhất,
> phù hợp cho mục đích nộp đồ án/demo giảng viên.
