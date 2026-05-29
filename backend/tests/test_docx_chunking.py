"""docx 分块：列表项不当标题、节级合并、小文档仍合并相邻段。"""

from app.core.chunking_engine import (
    adapt_chunk_size_for_small_doc,
    heading_path_for_merge,
    merge_adjacent_segments_by_budget,
    merge_orphan_document_title_with_next,
    merge_orphan_section_heading_with_next,
    split_segments_at_cn_section_headings,
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
    assert heading_path_for_merge("**一、适用对象** / **1、短条目**") == "一、适用对象"


def test_merge_orphan_document_title_with_next_section():
    segments = [
        _seg("新生儿“一件事”办理指南", block="heading", heading_path="新生儿“一件事”办理指南"),
        _seg("一、适用对象\n1、符合 A 条件", block="paragraph", heading_path="一、适用对象"),
        _seg("二、可联办事项\n1、《出生医学证明》", block="paragraph", heading_path="二、可联办事项"),
    ]
    merged = merge_orphan_document_title_with_next(segments)
    assert len(merged) == 2
    assert "新生儿“一件事”办理指南" in merged[0].text
    assert "一、适用对象" in merged[0].text
    assert merged[0].metadata.get("merged_document_title") == "新生儿“一件事”办理指南"


def test_merge_orphan_section_heading_into_next_body():
    """纯节级标题块（含章/节多级标题链）应向下并入紧随的正文段。"""
    segments = [
        _seg("第三章 刑罚 第一节 刑罚的种类", block="heading", heading_path="第三章 刑罚"),
        _seg(
            "第三十二条 刑罚分为主刑和附加刑，附加刑也可以独立适用。",
            block="paragraph",
            heading_path="第三章 刑罚",
        ),
    ]
    merged = merge_orphan_section_heading_with_next(segments)
    assert len(merged) == 1
    assert "第三章 刑罚" in merged[0].text
    assert "第三十二条" in merged[0].text
    assert merged[0].metadata.get("merged_section_heading")


def test_orphan_section_heading_not_merged_before_table():
    """标题块后紧跟表格原子块时保持原样，不破坏表格上下文合并逻辑。"""
    heading = _seg("附件2 设备配置表", block="heading", heading_path="附件2")
    table = ParsedSegment(
        text="| 场景 | 设备 |\n| --- | --- |\n| 门诊 | 摄像头 |",
        start_offset=0,
        end_offset=40,
        heading_path="附件2",
        metadata={"block": "table", "table_role": "body"},
    )
    merged = merge_orphan_section_heading_with_next([heading, table])
    assert len(merged) == 2
    assert merged[0].text == "附件2 设备配置表"


def test_section_with_list_items_is_not_orphan_heading():
    """已含列表正文的小节块不应被误判为纯标题而向下合并。"""
    section = _seg(
        "一、适用对象\n1、符合 A 条件\n2、符合 B 条件",
        block="heading",
        heading_path="一、适用对象",
    )
    nxt = _seg("二、可联办事项\n1、《出生医学证明》", block="heading", heading_path="二、可联办事项")
    merged = merge_orphan_section_heading_with_next([section, nxt])
    assert len(merged) == 2
    assert merged[0].text.startswith("一、适用对象")


def test_paren_enumeration_stays_with_article():
    """法条「…如下：（一）…（二）…」的括号枚举项不应被逐项硬切。"""
    big = ParsedSegment(
        text="第三十三条 主刑的种类如下：\n\n（一）管制；\n\n（二）拘役；\n\n（三）有期徒刑；\n\n（四）无期徒刑；",
        start_offset=0,
        end_offset=200,
        metadata={"block": "paragraph", "mineru_section_merge": True},
    )
    out = split_segments_at_cn_section_headings([big])
    assert len(out) == 1
    assert "（一）管制" in out[0].text
    assert "（四）无期徒刑" in out[0].text


def test_real_cn_section_still_split():
    """真正的 一、二、 节标题仍按节硬切，不受括号枚举放宽影响。"""
    big = ParsedSegment(
        text="一、适用对象\n申报人应为父母任意一方。\n二、办理材料\n需提供身份证与户口本。",
        start_offset=0,
        end_offset=200,
        metadata={"block": "paragraph", "mineru_section_merge": True},
    )
    out = split_segments_at_cn_section_headings([big])
    assert len(out) == 2
    assert "一、适用对象" in out[0].text and "二、办理材料" not in out[0].text
    assert "二、办理材料" in out[1].text


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
    merged = split_segments_at_cn_section_headings(merged)
    assert len(merged) < len(segments)
    section_one = next(s for s in merged if "一、适用对象" in s.text and "1、符合 A" in s.text)
    assert "2、符合 B" in section_one.text
    chunks = chunk_segments(merged, chunk_size, 10)
    assert len(chunks) < len(segments)
    assert not any(c.content.strip() == "一、适用对象" for c in chunks)
    assert not any(
        c.content.strip() == "新生儿“一件事”办理指南" and "一、适用对象" not in c.content for c in chunks
    )
