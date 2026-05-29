"""MinerU Markdown 加粗节标题 + 图片 OCR 整理的分块回归。"""

import json
from pathlib import Path

from app.core.chunking_engine import (
    consolidate_mineru_image_segments,
    heading_path_for_merge,
    merge_leading_preamble_segments,
    merge_mineru_segments_by_section,
    prepare_mineru_prebuilt_segments,
    split_segments_at_cn_section_headings,
)
from app.core.document_parser import ParsedSegment, _update_heading_path
from app.core.heading_match import heading_starts_body, normalize_heading_match_text
from app.core.mineru_gateway import MineruResult, _text_level_to_class
from app.core.text_chunker import segments_to_chunk_candidates


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


def _image(ocr: str, *, start: int, path: str | None = None) -> ParsedSegment:
    return ParsedSegment(
        text=ocr,
        start_offset=start,
        end_offset=start + len(ocr),
        heading_path=path,
        metadata={"block": "image", "img_path": "images/x.png", "image_ocr_text": ocr},
    )


def test_markdown_bold_section_heading_recognized():
    assert heading_starts_body("**一、适用对象**") is True
    assert heading_starts_body("一、适用对象") is True
    assert normalize_heading_match_text("**二、可联办事项**") == "二、可联办事项"
    assert heading_path_for_merge("**一、适用对象** / 1、条目") == "一、适用对象"


def test_preamble_stops_before_markdown_section():
    segments = [
        _para("新生儿出生“一件事”办理指南", "新生儿出生“一件事”办理指南", start=0),
        _heading("**一、适用对象**", "一、适用对象", start=20),
        _para("1、申报人应为新生儿父母任意一方。", "一、适用对象", start=40),
    ]
    merged = merge_leading_preamble_segments(segments)
    assert len(merged) == 3
    assert merged[0].text == "新生儿出生“一件事”办理指南"
    assert (merged[0].metadata or {}).get("block") != "document_preamble"
    assert merged[1].text == "**一、适用对象**"


def test_split_oversized_merged_section_block_single_newline():
    """单换行合并段（full_text 常见）也应硬切各节。"""
    parts = [
        "新生儿出生“一件事”办理指南",
        "**一、适用对象**",
        "1、申报人应为新生儿父母任意一方。",
        "**二、可联办事项（已办理公安落户的暂不再支持线上办理）**",
        "1、《出生医学证明》签发办理",
        "**三、可享受的延伸服务**",
        "1、生育医疗费支付（含产前检查费）",
        "**四、需提供材料**",
        "1、中华人民共和国结婚证",
    ]
    big = ParsedSegment(
        text="\n".join(parts),
        start_offset=0,
        end_offset=500,
        metadata={"block": "paragraph", "mineru_section_merge": True},
    )
    split = split_segments_at_cn_section_headings([big])
    assert len(split) == 4
    assert "新生儿出生“一件事”办理指南" in split[0].text
    assert "一、适用对象" in split[0].text
    assert "二、可联办事项" in split[1].text
    assert "三、可享受的延伸服务" in split[2].text
    assert "四、需提供材料" in split[3].text


def test_split_oversized_merged_section_block():
    """565 字含一～四节的大块应被硬切为标题 + 各节。"""
    parts = [
        "新生儿出生“一件事”办理指南",
        "**一、适用对象**",
        "1、申报人应为新生儿父母任意一方。",
        "**二、可联办事项（已办理公安落户的暂不再支持线上办理）**",
        "1、《出生医学证明》签发办理",
        "**三、可享受的延伸服务**",
        "1、生育医疗费支付（含产前检查费）",
        "**四、需提供材料**",
        "1、中华人民共和国结婚证",
    ]
    big = ParsedSegment(
        text="\n\n".join(parts),
        start_offset=0,
        end_offset=500,
        metadata={"block": "paragraph", "mineru_section_merge": True},
    )
    split = split_segments_at_cn_section_headings([big])
    assert len(split) == 4
    assert "新生儿出生“一件事”办理指南" in split[0].text
    assert "一、适用对象" in split[0].text
    assert "二、可联办事项" in split[1].text
    assert "三、可享受的延伸服务" in split[2].text
    assert "四、需提供材料" in split[3].text


def test_newborn_guide_sections_chunk_one_per_section():
    """用户案例：一～四节应各成一块，不应把二、三、四节吞进文前。"""
    items = [
        {"type": "text", "text": "新生儿出生“一件事”办理指南", "page_idx": 0},
        {"type": "text", "text": "**一、适用对象**", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "1、申报人应为新生儿父母任意一方。", "page_idx": 0},
        {"type": "text", "text": "2、新生儿落户必须随父母中河南户籍一方，集体户口、父母所属民族不一致、非婚内出生的新生儿暂不支持一件事联办。", "page_idx": 0},
        {"type": "text", "text": "3、新生儿父母任意一方为军人的暂不支持一件事联办。", "page_idx": 0},
        {"type": "text", "text": "4、新生儿已线下办理过入户的暂不支持一件事联办。", "page_idx": 0},
        {"type": "text", "text": "5、新生儿父母必须为河南省内办理的婚姻登记，且当前为婚姻存续状态。", "page_idx": 0},
        {"type": "text", "text": "6、新生儿在河南省内助产机构出生，年龄不大于12个月，新生儿母亲在入院时已进行人证核验。", "page_idx": 0},
        {"type": "text", "text": "**二、可联办事项（已办理公安落户的暂不再支持线上办理）**", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "1、《出生医学证明》签发办理", "page_idx": 0},
        {"type": "text", "text": "2、预防接种证办理", "page_idx": 0},
        {"type": "text", "text": "3、对新出生婴儿办理出生登记（国内出生）", "page_idx": 0},
        {"type": "text", "text": "4、城乡居民参保登记（新生儿）", "page_idx": 0},
        {"type": "text", "text": "5、社会保障卡申领", "page_idx": 0},
        {"type": "text", "text": "**三、可享受的延伸服务**", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "1、生育医疗费支付（含产前检查费）", "page_idx": 0},
        {"type": "text", "text": "2、生育津贴支付", "page_idx": 0},
        {"type": "text", "text": "3、科学育儿指导服务", "page_idx": 0},
        {"type": "text", "text": "**四、需提供材料**", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "1、中华人民共和国结婚证", "page_idx": 0},
        {"type": "text", "text": "2、中华人民共和国居民身份证", "page_idx": 0},
    ]

    segments: list[ParsedSegment] = []
    parts: list[str] = []
    offset = [0]
    stack: list[tuple[str, str]] = []
    path: str | None = None

    def append(text: str, meta: dict) -> None:
        start, end = offset[0], offset[0] + len(text)
        segments.append(
            ParsedSegment(
                text=text,
                start_offset=start,
                end_offset=end,
                page_no=1,
                heading_path=path,
                metadata=meta,
            )
        )
        parts.append(text)
        offset[0] = end + 1

    for item in items:
        typ = item["type"]
        if typ != "text":
            continue
        tl = item.get("text_level")
        text = item["text"]
        if tl:
            cls = _text_level_to_class(tl)
            path = _update_heading_path(stack, cls, normalize_heading_match_text(text))
            append(text, {"block": "heading", "heading_path": path})
        else:
            append(text, {"block": "paragraph", "heading_path": path})

    full = "\n".join(parts)
    segs = merge_leading_preamble_segments(segments, full_text=full)
    segs = consolidate_mineru_image_segments(segs)
    merged, _ = prepare_mineru_prebuilt_segments(
        segs,
        512,
        parser_type="docx",
        parser_backend="mineru",
    )
    chunks = segments_to_chunk_candidates(merged)

    assert len(chunks) >= 4
    section_one = next(c for c in chunks if "一、适用对象" in c.content and "1、申报人" in c.content)
    section_two = next(c for c in chunks if "二、可联办事项" in c.content and "出生医学证明" in c.content)
    section_three = next(c for c in chunks if "三、可享受的延伸服务" in c.content)
    section_four = next(c for c in chunks if "四、需提供材料" in c.content)
    assert "二、可联办事项" not in section_one.content
    assert "三、可享受的延伸服务" not in section_two.content
    assert "四、需提供材料" not in section_three.content
    assert "五、" not in section_four.content
    assert all("申报须知" not in c.content or "五、" in c.content for c in chunks[:4])


def test_newborn_guide_full_content_list_fixture():
    """用户完整 MinerU JSON：标题 + 一～四节各一块；短 UI OCR 不 orphan。"""
    fixture = Path(__file__).resolve().parent / "fixtures" / "newborn_guide_content_list.json"
    content_list = json.loads(fixture.read_text(encoding="utf-8"))
    doc = MineruResult(content_list=content_list, source_file_name="newborn.docx").to_parsed_document()

    segs = merge_leading_preamble_segments(doc.segments, full_text=doc.text)
    segs = consolidate_mineru_image_segments(segs)
    merged, _ = prepare_mineru_prebuilt_segments(
        segs,
        512,
        parser_type="docx",
        parser_backend="mineru",
    )
    chunks = segments_to_chunk_candidates(merged)

    assert len(chunks) < 65
    assert "新生儿出生“一件事”办理指南" in chunks[0].content
    assert "一、适用对象" in chunks[0].content
    assert "二、可联办事项" not in chunks[0].content
    assert "二、可联办事项" in chunks[1].content and "三、可享受" not in chunks[1].content
    assert "三、可享受的延伸服务" in chunks[2].content
    assert "四、需提供材料" in chunks[3].content
    assert "五、移动端办理流程" in chunks[4].content
    assert "以下地区支持办理该事项，请选择：" in chunks[4].content
    assert not any(c.content.strip() == "以下地区支持办理该事项，请选择：" for c in chunks)
    assert not any("河南省 Q、社保缴费" in c.content and "一、适用对象" in c.content for c in chunks)


def test_short_ui_image_ocr_attached_to_previous_step():
    step = _para(
        "1.登录豫事办App，点击新生儿出生“一件事”，选择办理地区。",
        "**五、移动端办理流程**",
        start=0,
    )
    img = _image("以下地区支持办理该事项，请选择：", start=100, path="**五、移动端办理流程**")
    out = consolidate_mineru_image_segments([step, img])
    assert len(out) == 1
    assert "以下地区支持办理该事项，请选择：" in out[0].text
    assert (out[0].metadata or {}).get("image_ocr_attached") == 1


def test_duplicate_notice_ocr_dropped():
    notice = _para(
        "1.登录豫事办App，阅读申报须知，表单填写过程中系统将会调用申报人及其配偶的身份、婚姻、户籍信息。",
        "**五、移动端办理流程**",
        start=0,
    )
    long_ocr = _image(
        "## 申报须知 1.申报人应为新生儿父母任意一方。"
        "2.新生儿落户必须随父母中河南户籍一方。"
        "3.表单填写过程中系统将会调用申报人及其配偶的身份、婚姻、户籍信息。",
        start=200,
    )
    out = consolidate_mineru_image_segments([notice, long_ocr])
    assert len(out) == 1


def test_form_menu_ocr_attached_to_step_paragraph():
    step = _para(
        "2.填写表单信息，确认无误后提交。",
        "**五、移动端办理流程**",
        start=0,
    )
    form_ocr = _image(
        "## 表单\n是 / 否\n是 / 否\n是 / 否\n是 / 否",
        start=100,
        path="**五、移动端办理流程**",
    )
    out = consolidate_mineru_image_segments([step, form_ocr])
    assert len(out) == 1
    assert "## 表单" in out[0].text
    meta = out[0].metadata or {}
    assert meta.get("chunk_role") == "step_with_ocr"
    assert meta.get("retrieval_policy") == "normal"


def test_standalone_image_gets_retrieval_metadata():
    img = _image("较长的独立界面说明文字" * 5, start=0)
    out = consolidate_mineru_image_segments([img])
    assert len(out) == 1
    meta = out[0].metadata or {}
    assert meta.get("chunk_role") == "image_ocr"
    assert meta.get("retrieval_policy") == "exclude_by_default"
