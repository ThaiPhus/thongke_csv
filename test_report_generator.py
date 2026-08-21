"""
test_report_generator.py
-------------------------
Unit test cho report_generator.py: escape HTML, nội dung báo cáo đầy đủ.
"""

from report_generator import build_html_report, save_html_report


def _fake_result(group_by_key=None):
    result = {
        "rows_read": 1000,
        "elapsed_seconds": 1.23,
        "overall": {
            "count_valid": 950,
            "count_invalid": 50,
            "sum": 1_000_000.0,
            "mean": 1052.6,
            "min": 10.0,
            "max": 9999.0,
            "stddev": 500.5,
        },
    }
    if group_by_key:
        result["by_group"] = {
            "A": {"count_valid": 500, "mean": 1000.0, "min": 10.0, "max": 5000.0},
            "B": {"count_valid": 450, "mean": 1100.0, "min": 20.0, "max": 9999.0},
        }
    return result


class TestHtmlEscaping:
    def test_script_tag_in_group_name_is_escaped(self):
        """BUG (đã sửa): tên nhóm/cột chứa ký tự HTML đặc biệt từng làm vỡ layout báo cáo."""
        result = _fake_result()
        result["by_group"] = {
            "<script>alert(1)</script>": {"count_valid": 10, "mean": 1.0, "min": 1.0, "max": 1.0},
        }
        html = build_html_report("file.csv", "col", result, {}, group_by="grp")
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_ampersand_in_filename_is_escaped(self):
        result = _fake_result()
        html = build_html_report("A&B<Corp>.csv", "col", result, {})
        assert "A&B<Corp>.csv" not in html
        assert "A&amp;B" in html

    def test_no_group_by_omits_group_section(self):
        result = _fake_result()
        html = build_html_report("f.csv", "col", result, {})
        assert "Thống kê theo" not in html


class TestReportContent:
    def test_contains_key_stats(self):
        result = _fake_result()
        html = build_html_report("f.csv", "col", result, {})
        assert "950" in html  # count_valid
        assert "1,000,000" in html or "1000000" in html  # sum

    def test_charts_embedded_as_base64_images(self):
        result = _fake_result()
        fake_chart = "data:image/png;base64,iVBORw0KGgo="
        html = build_html_report("f.csv", "col", result, {"Biểu đồ test": fake_chart})
        assert fake_chart in html
        assert html.count("<img") == 1

    def test_chart_title_not_duplicated(self):
        """Tiêu đề biểu đồ chỉ nên xuất hiện 1 lần (bên trong ảnh), không lặp lại <h3>."""
        result = _fake_result()
        html = build_html_report("f.csv", "col", result, {"Biểu đồ ABC": "data:image/png;base64,xx"})
        assert "<h3>Biểu đồ ABC</h3>" not in html


class TestSaveHtmlReport:
    def test_writes_file_correctly(self, tmp_path):
        out_path = tmp_path / "report.html"
        save_html_report("<html>test</html>", str(out_path))
        assert out_path.read_text(encoding="utf-8") == "<html>test</html>"

    def test_creates_parent_directories(self, tmp_path):
        out_path = tmp_path / "sub" / "dir" / "report.html"
        save_html_report("<html>x</html>", str(out_path))
        assert out_path.exists()
