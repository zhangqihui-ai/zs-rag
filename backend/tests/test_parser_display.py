"""解析器展示名称。"""

from app.core.parser_config import parser_engine_display_name


def test_html_table_fallback_label():
    assert parser_engine_display_name("html_table", fallback=True) == "HTML 表格（降级）"
