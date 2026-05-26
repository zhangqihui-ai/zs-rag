"""docx 分块：列表项不当标题、节级合并、小文档仍合并相邻段。"""

from app.core.chunking_engine import (
    adapt_chunk_size_for_small_doc,
    heading_path_for_merge,
    merge_adjacent_segments_by_budget,
)
from app.core.document_parser import ParsedSegment, _detect_heading_class
from app.core.text_chunker import chunk_segments


def _seg(text: str, *, block: str = "paragraph", heading_path: str | None = None) -> ParsedSegment:
    meta: dict = {"block": block, "heading_path": heading_path}
    if block == "heading":
        meta["heading_class"] = "chapter"
    return ParsedSegment(
        text=text,
        start_offset=0,
        end_offset=len(text),
        heading_path=heading_path,
        metadata=meta,
    )


def test_enumeration_line_not_heading_without_word_style():
    assert _detect_heading_class("1、《出生医学证明》签发办理", None) is None
    assert _detect_heading_class("2. 符合办理条件", None) is None
    assert _detect_heading_class("一、适用对象", None) == "chapter"


def test_heading_path_for_merge_uses_section_marker():
    assert heading_path_for_merge("新生儿一件事办理指南 / 一、适用对象") == "一、适用对象"
    assert heading_path_for_merge("一、适用对象 / 1、短条目") == "一、适用对象"
    assert heading_path_for_merge("二、可联办事项") == "二、可联办事项"


def test_merge_guide_sections_under_budget():
    segments = [
        _seg("新生儿“一件事”办理指南", block="heading", heading_path="新生儿“一件事”办理指南"),
        _seg("一、适用对象", block="heading", heading_path="一、适用对象"),
        _seg("1、符合 A 条件", heading_path="一、适用对象"),
        _seg("2、符合 B 条件", heading_path="一、适用对象"),
        _seg("3、符合 C 条件", heading_path="一、适用对象"),
        _seg("二、可联办事项", block="heading", heading_path="二、可联办事项"),
        _seg("1、《出生医学证明》签发办理", heading_path="二、可联办事项"),
    ]
    chunk_size, _ = adapt_chunk_size_for_small_doc(segments, 1024, 50)
    assert chunk_size < 1024
    merged = merge_adjacent_segments_by_budget(segments, chunk_size)
    assert len(merged) < len(segments)
    section_one = next(s for s in merged if "一、适用对象" in s.text and "1、符合 A" in s.text)
    assert "2、符合 B" in section_one.text
    chunks = chunk_segments(merged, chunk_size, 10)
    assert len(chunks) < len(segments)
    assert not any(c.content.strip() == "一、适用对象" for c in chunks)
