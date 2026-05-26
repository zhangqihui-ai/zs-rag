"""Word 解析视图导出测试。"""

from app.core.docx_view_export import (
    assign_docx_block_indices,
    build_docx_content_list,
    build_docx_markdown,
    sync_docx_page_metadata,
    table_blocks_from_content_list,
)
from app.core.document_parser import ParsedSegment


def _seg(text: str, **meta) -> ParsedSegment:
    page_no = meta.pop("page_no", None)
    return ParsedSegment(text=text, start_offset=0, end_offset=len(text), page_no=page_no, metadata=meta)


def test_assign_block_indices_and_export():
    segments = [
        _seg("一、适用对象", block="heading", heading_class="chapter", page_no=1),
        _seg("1、条件 A", block="paragraph", page_no=1),
        _seg("列1：a；列2：b", block="table", table_role="row", page_no=2),
    ]
    assign_docx_block_indices(segments)
    sync_docx_page_metadata(segments)
    assert (segments[0].metadata or {}).get("block_index") == 0
    cl = build_docx_content_list(segments)
    assert len(cl) == 3
    assert cl[0]["block_index"] == 0
    assert cl[0]["type"] == "title"
    assert cl[0].get("page_idx") == 0
    assert cl[0].get("page_no") == 1
    assert cl[2].get("page_no") == 2
    md = build_docx_markdown(segments)
    assert "[第1页]" in md
    assert "[第2页]" in md
    assert "## 一、适用对象" in md
    tables = table_blocks_from_content_list(cl)
    assert len(tables) == 1
