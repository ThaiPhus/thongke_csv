# Đề tài 2: Tính toán thống kê từ file CSV lớn (doanh thu theo ngày)

Chương trình đọc file CSV **doanh thu theo ngày** có kích thước lớn và tính
**trung bình, min, max, độ lệch chuẩn**, tối ưu để không tràn RAM — bám theo
đúng "CẤU TRÚC ĐỒ ÁN MÔN HỌC" bạn đã có (tối ưu bộ nhớ, Streaming/Generator,
hướng mở rộng lên Pandas/Spark). Có giao diện web cho phép **chọn file từ
máy tính**, **trực quan hoá** và **xuất báo cáo HTML**.

## Cấu trúc thư mục

```
thongke_csv/
├── app.py                  # ⭐ Ứng dụng WEB (Streamlit): upload file, biểu đồ, xuất HTML
├── analytics.py            # Hàm phân tích dùng chung: histogram, xu hướng theo thời gian
├── charts.py                # Vẽ biểu đồ (bar/histogram/line/pie) -> ảnh base64
├── report_generator.py     # Sinh file báo cáo HTML tự chứa (nhúng sẵn biểu đồ)
├── generate_data.py        # Sinh dữ liệu CSV mẫu (doanh thu theo ngày)
├── stats_stream.py         # CLI cách 1: thuần Python, Generator + Welford's algorithm (RAM thấp)
├── stats_pandas_chunk.py   # CLI cách 2: Pandas + chunksize, kiểu MapReduce (nhanh hơn)
├── benchmark.py            # Đo & so sánh thời gian / RAM giữa 2 cách CLI
└── data/                   # Dữ liệu CSV sinh ra
```

## Cách chạy

### A. Ứng dụng web (khuyến nghị — có upload file, biểu đồ, xuất HTML)

```bash
pip install streamlit pandas matplotlib numpy
streamlit run app.py
```

Trình duyệt sẽ tự mở tại `http://localhost:8501`. Các bước sử dụng:
1. Bấm **"Chọn file CSV từ máy tính của bạn"** để tải file dữ liệu lên.
2. Chọn cột số cần thống kê, cột để nhóm (vd: `khu_vuc`), cột thời gian (vd: `ngay`).
3. Bấm **"Chạy phân tích"** → xem bảng thống kê + 4 loại biểu đồ (cột, tròn, histogram, đường xu hướng).
4. Bấm **"Tải báo cáo HTML"** để tải file báo cáo hoàn chỉnh (đính kèm được vào Phụ lục đồ án).

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
- 1.4 Công nghệ sử dụng: Python (`csv`, `dataclasses`), Pandas.

**Chương 2 – Phân tích bài toán**
- 2.2 Phân tích dữ liệu: cột `doanh_thu` (số), có ~0.5% giá trị thiếu để mô
  phỏng dữ liệu thực tế cần làm sạch.

**Chương 3 – Xây dựng chương trình**
- 3.1 Môi trường: Python 3, thư viện Pandas, Streamlit (giao diện web),
  Matplotlib (trực quan hoá), NumPy (histogram).
- 3.3 Thuật toán: **Welford's online algorithm** — tính mean/variance theo
  từng dòng, độ phức tạp O(1) bộ nhớ, không cần giữ toàn bộ dữ liệu để tính
  lại tổng bình phương (tránh sai số/tràn số so với công thức thô). Ngoài ra,
  `analytics.py` dùng kỹ thuật **histogram streaming 2 lượt đọc** (lượt 1 lấy
  min/max, lượt 2 cộng dồn `np.histogram` từng chunk) để vẽ được biểu đồ phân
  phối mà không cần giữ toàn bộ cột dữ liệu trong RAM.
- 3.4 Cài đặt: `stats_stream.py` (generator) vs `stats_pandas_chunk.py`
  (kiểu Map–Reduce: mỗi chunk tính cục bộ rồi gộp lại). `app.py` là giao diện
  web cho phép người dùng chọn file CSV từ máy tính (`st.file_uploader`),
  cấu hình cột phân tích, xem 4 loại biểu đồ (cột, tròn, histogram, đường xu
  hướng theo thời gian — module `charts.py`) và xuất báo cáo HTML tự chứa
  (module `report_generator.py`, biểu đồ nhúng dạng base64 nên không phụ
  thuộc file ngoài khi mở lại).

## 🚀 Đưa ứng dụng lên hosting (deploy)

### Cách 1: Streamlit Community Cloud (miễn phí, khuyến nghị cho đồ án)

**Bước 1 — Đưa code lên GitHub**
1. Tạo một repository mới trên GitHub (public hoặc private đều được).
2. Đẩy toàn bộ thư mục `thongke_csv/` lên repo đó (đã có sẵn `requirements.txt`
   và `.gitignore` trong project này, không cần tạo thêm):
   ```bash
   cd thongke_csv
   git init
   git add .
   git commit -m "Đồ án: chương trình thống kê CSV"
   git branch -M main
   git remote add origin https://github.com/<ten-github>/<ten-repo>.git
   git push -u origin main
   ```

**Bước 2 — Deploy**
1. Vào **https://share.streamlit.io** → đăng nhập bằng tài khoản GitHub.
2. Bấm **"New app"** → chọn repo vừa đẩy lên.
3. Điền:
   - Branch: `main`
   - Main file path: `app.py`
4. Bấm **Deploy**. Sau khoảng 1–2 phút sẽ có link dạng
   `https://<ten-app>.streamlit.app` để chia sẻ/nộp kèm đồ án.

Mỗi khi bạn `git push` code mới, app sẽ tự động build lại — không cần thao tác thủ công.

**Giới hạn cần biết:** gói miễn phí cho phép upload file tối đa theo cấu hình
trong `.streamlit/config.toml` (đã đặt 500MB), và app sẽ "ngủ" nếu không có
người dùng trong một thời gian — chỉ cần mở lại link là app tự khởi động.

### Cách 2: Hugging Face Spaces (miễn phí, cũng hỗ trợ Streamlit)

1. Tạo Space mới tại **https://huggingface.co/new-space**, chọn SDK = **Streamlit**.
2. Upload các file trong `thongke_csv/` (kể cả `requirements.txt`) vào Space
   (qua giao diện web hoặc `git push` như Hugging Face hướng dẫn).
3. Space tự động build và chạy `app.py`, cho một link công khai dạng
   `https://huggingface.co/spaces/<ten-user>/<ten-space>`.

### Cách 3: Render.com (miễn phí có giới hạn, phù hợp nếu muốn thêm domain riêng)

1. Đẩy code lên GitHub như Cách 1.
2. Vào **https://render.com** → **New Web Service** → kết nối repo GitHub.
3. Cấu hình:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
4. Bấm **Create Web Service** để deploy.

> Cách 1 (Streamlit Community Cloud) là đơn giản nhất và miễn phí hoàn toàn,
> nên dùng cho mục đích nộp đồ án/demo giảng viên.

**Chương 4 – Thực nghiệm và đánh giá**
- Dùng `generate_data.py` để tạo file 100MB / 500MB / 1GB.
- Dùng `benchmark.py` để đo Execution Time và Peak Memory Usage
  (bằng `tracemalloc`), lập bảng/biểu đồ so sánh hai cách cài đặt.
- Nhận xét: streaming tối ưu RAM tuyệt đối nhưng chậm hơn do xử lý từng
  dòng bằng Python thuần; Pandas vector hóa nên nhanh hơn đáng kể nhưng
  RAM tăng theo kích thước mỗi chunk.

**Hướng phát triển**: chuyển `stats_pandas_chunk.py` sang PySpark
(`df.groupBy().agg()`) để chạy phân tán trên cluster khi dữ liệu lên
hàng chục/hàng trăm GB — đúng hướng đã nêu trong file cấu trúc đồ án.

## Ghi chú xử lý dữ liệu bẩn
Cả hai chương trình đều tự động bỏ qua (và đếm số lượng) các dòng có giá trị
rỗng/không parse được ở cột thống kê, thay vì làm crash chương trình —
tương ứng với đặc trưng **Veracity** đã nêu trong slide "Tổng quan về Big
Data".
