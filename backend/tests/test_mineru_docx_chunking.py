"""MinerU 小文档 + 整表分段：避免 overlap 重复切块。"""

from app.core.chunking_engine import (
    adapt_chunk_size_for_small_doc,
    merge_adjacent_segments_by_budget,
    merge_mineru_segments_by_section,
    mineru_segment_is_atomic,
)
from app.core.document_parser import ParsedSegment
from app.core.text_chunker import chunk_segments, segments_to_chunk_candidates


def _heading(text: str, path: str, *, start: int = 0) -> ParsedSegment:
    return ParsedSegment(
        text=text,
        start_offset=start,
        end_offset=start + len(text),
        heading_path=path,
        metadata={"block": "heading", "heading_path": path},
    )


def _para(text: str, path: str, *, start: int) -> ParsedSegment:
    return ParsedSegment(
        text=text,
        start_offset=start,
        end_offset=start + len(text),
        heading_path=path,
        metadata={"block": "paragraph", "heading_path": path},
    )


def _image(text: str, *, start: int) -> ParsedSegment:
    return ParsedSegment(
        text=text,
        start_offset=start,
        end_offset=start + len(text),
        metadata={"block": "image", "img_path": "images/a.png"},
    )


def _preamble() -> ParsedSegment:
    text = "**河南公司** **政务数据智能编目系统能力** **验收测试情况说明**"
    return ParsedSegment(
        text=text,
        start_offset=0,
        end_offset=len(text),
        metadata={"block": "document_preamble", "preamble_segment_count": 3},
    )


def _table_body() -> ParsedSegment:
    text = "| 能力基本信息 | 能力名称 | 政务数据智能编目系统能力 |\n| --- | --- | --- |\n| 服务名称 | a | b |"
    return ParsedSegment(
        text=text,
        start_offset=100,
        end_offset=100 + len(text),
        metadata={"block": "table", "table_role": "body", "table_index": 0, "parser_backend": "mineru"},
    )


class _FakeParsed:
    def __init__(self, segments, metadata=None):
        self.segments = segments
        self.metadata = metadata or {"parser_backend": "mineru"}
        self.parser_type = "docx"


def _parsed_uses_prebuilt_table_chunks(parsed) -> bool:
    meta = parsed.metadata if isinstance(parsed.metadata, dict) else {}
    segs = parsed.segments or []
    if any((s.metadata or {}).get("table_role") == "body" for s in segs):
        return True
    if meta.get("parser_backend") in {"mineru", "opendataloader"} and segs:
        return True
    return False


def test_mineru_docx_uses_prebuilt_chunks():
    segs = [_preamble(), _table_body()]
    parsed = _FakeParsed(segs)
    assert _parsed_uses_prebuilt_table_chunks(parsed) is True
    chunks = segments_to_chunk_candidates(segs)
    assert len(chunks) == 2
    assert chunks[1].metadata.get("table_role") == "body"


def test_general_path_does_not_split_table_with_overlap():
    """未走 prebuilt 时，表格段也应原子输出，避免 overlap 重复切块。"""
    segs = [_preamble(), _table_body()]
    chunk_size, overlap = adapt_chunk_size_for_small_doc(segs, 1024, 80)
    merged = merge_adjacent_segments_by_budget(segs, chunk_size)
    chunks = chunk_segments(merged, chunk_size, overlap)
    assert len(chunks) <= 2
    table_hits = sum(1 for c in chunks if "| 服务名称 |" in c.content)
    assert table_hits == 1


def test_merge_mineru_docx_section_merges_list_items():
    path = "一、适用对象"
    segs = [
        _heading("一、适用对象", path, start=0),
        _para("1、申报人应为新生儿父母任意一方。", path, start=20),
        _para("2、新生儿落户必须随父母中河南户籍一方。", path, start=50),
        _para("3、新生儿父母任意一方为军人的暂不支持。", path, start=90),
    ]
    merged = merge_mineru_segments_by_section(segs, budget=512)
    assert len(merged) == 1
    assert "1、申报人" in merged[0].text
    assert "3、新生儿父母" in merged[0].text
    assert merged[0].metadata.get("merged_segment_count") == 4


def test_merge_mineru_docx_keeps_image_atomic():
    path = "五、移动端办理流程"
    segs = [
        _heading("五、移动端办理流程", path, start=0),
        _para("1.登录豫事办App", path, start=20),
        _image("豫事办 推荐服务 新生儿出生", start=80),
        _para("2.引导式申报", path, start=200),
    ]
    merged = merge_mineru_segments_by_section(segs, budget=512)
    assert len(merged) == 2
    assert merged[0].metadata.get("block") == "image"
    assert "豫事办" in merged[0].text
    assert "1.登录豫事办App" in merged[0].text
    assert "2.引导式申报" in merged[1].text


def test_merge_mineru_docx_keeps_table_atomic():
    segs = [
        _para("说明文字", "一、章节", start=0),
        _table_body(),
    ]
    merged = merge_mineru_segments_by_section(segs, budget=512)
    assert len(merged) == 1
    assert merged[0].metadata.get("table_role") == "body"
    assert "说明文字" in merged[0].text
