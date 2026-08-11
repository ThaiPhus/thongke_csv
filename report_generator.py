"""
report_generator.py
--------------------
Sinh báo cáo phân tích dạng file HTML độc lập (self-contained):
    - Không phụ thuộc file CSS/JS ngoài, không cần internet để mở lại.
    - Biểu đồ được nhúng trực tiếp dạng base64 trong thẻ <img>.
    - Có thể mở bằng bất kỳ trình duyệt nào, hoặc đính kèm vào Phụ lục đồ án.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional


def _stats_table_html(overall: dict) -> str:
    rows = [
        ("Số dòng hợp lệ", f"{overall['count_valid']:,}"),
        ("Số dòng lỗi/thiếu", f"{overall['count_invalid']:,}"),
        ("Tổng (sum)", f"{overall['sum']:,}"),
        ("Trung bình (mean)", f"{overall['mean']:,}"),
        ("Nhỏ nhất (min)", f"{overall['min']:,}"),
        ("Lớn nhất (max)", f"{overall['max']:,}"),
        ("Độ lệch chuẩn", f"{overall['stddev']:,}"),
    ]
    body = "\n".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows)
    return f"<table class='stats-table'><tbody>{body}</tbody></table>"


def _group_table_html(by_group: dict) -> str:
    header = "<tr><th>Nhóm</th><th>Số lượng</th><th>Trung bình</th><th>Nhỏ nhất</th><th>Lớn nhất</th></tr>"
    rows = []
    for key, s in by_group.items():
        rows.append(
            f"<tr><td>{key}</td><td>{int(s.get('count_valid', 0)):,}</td>"
            f"<td>{s.get('mean', 0):,.2f}</td><td>{s.get('min', 0):,.2f}</td>"
            f"<td>{s.get('max', 0):,.2f}</td></tr>"
        )
    return f"<table class='stats-table'>{header}{''.join(rows)}</table>"


def build_html_report(
    file_name: str,
    column: str,
    result: dict,
    charts: dict,
    group_by: Optional[str] = None,
) -> str:
    """
    Tạo chuỗi HTML báo cáo hoàn chỉnh.

    charts: dict tên_biểu_đồ -> base64 data URI (lấy từ charts.py)
    """
    overall = result["overall"]
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    chart_sections = ""
    for title, data_uri in charts.items():
        # Không thêm tiêu đề <h3> ở đây vì tiêu đề đã được vẽ sẵn bên trong
        # chính hình ảnh (ax.set_title) — tránh hiển thị trùng lặp 2 lần.
        chart_sections += f"""
        <div class="chart-block">
            <img src="{data_uri}" alt="{title}" />
        </div>
        """

    group_section = ""
    if group_by and "by_group" in result:
        group_section = f"""
        <h2>Thống kê theo &quot;{group_by}&quot;</h2>
        {_group_table_html(result["by_group"])}
        """

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8" />
<title>Báo cáo thống kê dữ liệu - {file_name}</title>
<style>
    body {{
        font-family: 'Segoe UI', Arial, sans-serif;
        margin: 0; padding: 0 0 60px 0;
        background: #f4f6f8; color: #222;
    }}
    header {{
        background: linear-gradient(135deg, #1B4F72, #2E86AB);
        color: white; padding: 28px 40px;
    }}
    header h1 {{ margin: 0 0 6px 0; font-size: 26px; }}
    header p {{ margin: 2px 0; font-size: 14px; opacity: 0.9; }}
    .container {{ max-width: 960px; margin: 0 auto; padding: 24px 20px; }}
    section {{
        background: white; border-radius: 10px; padding: 22px 26px;
        margin-bottom: 22px; box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}
    h2 {{ color: #1B4F72; border-bottom: 2px solid #eee; padding-bottom: 8px; }}
    table.stats-table {{
        border-collapse: collapse; width: 100%; margin-top: 10px; font-size: 14px;
    }}
    table.stats-table th, table.stats-table td {{
        border: 1px solid #e0e0e0; padding: 8px 12px; text-align: left;
    }}
    table.stats-table th {{ background: #F0F4F8; }}
    table.stats-table tr:nth-child(even) {{ background: #FAFBFC; }}
    .chart-block {{ margin: 18px 0; text-align: center; }}
    .chart-block img {{ max-width: 100%; border-radius: 6px; }}
    .meta {{ color: #666; font-size: 13px; }}
    footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 30px; }}
</style>
</head>
<body>
<header>
    <h1>Báo cáo phân tích thống kê dữ liệu CSV</h1>
    <p>Tệp dữ liệu: <strong>{file_name}</strong> &nbsp;|&nbsp; Cột phân tích: <strong>{column}</strong></p>
    <p>Thời gian tạo báo cáo: {generated_at}</p>
</header>
<div class="container">

    <section>
        <h2>1. Thông tin xử lý</h2>
        <table class="stats-table">
            <tr><td>Số dòng đã đọc</td><td>{result['rows_read']:,}</td></tr>
            <tr><td>Thời gian xử lý</td><td>{result['elapsed_seconds']} giây</td></tr>
        </table>
    </section>

    <section>
        <h2>2. Thống kê tổng quan</h2>
        {_stats_table_html(overall)}
    </section>

    {"<section>" + group_section + "</section>" if group_section else ""}

    <section>
        <h2>3. Trực quan hoá dữ liệu</h2>
        {chart_sections}
    </section>

</div>
<footer>
    Báo cáo được sinh tự động bởi chương trình Phân tích dữ liệu lớn từ CSV — Đồ án môn học.
</footer>
</body>
</html>
"""
    return html


def save_html_report(html: str, output_path: str) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return str(path.resolve())
