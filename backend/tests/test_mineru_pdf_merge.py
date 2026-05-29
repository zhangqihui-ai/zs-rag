"""MinerU PDF 章节合并与 layout 噪声过滤。"""

from app.core.chunking_engine import (
    merge_leading_preamble_segments,
    merge_mineru_segments_by_section,
    mineru_merged_text_is_retrievable,
    mineru_text_is_layout_noise,
    prepare_mineru_prebuilt_segments,
    structured_parser_should_merge_sections,
)
from app.core.document_parser import ParsedSegment


def _seg(
    text: str,
    *,
    start: int,
    block: str = "paragraph",
    path: str | None = None,
    page: int | None = 1,
) -> ParsedSegment:
    return ParsedSegment(
        text=text,
        start_offset=start,
        end_offset=start + len(text),
        page_no=page,
        heading_path=path,
        metadata={"block": block, "heading_path": path},
    )


def test_layout_noise_detection():
    assert mineru_text_is_layout_noise("报")
    assert mineru_text_is_layout_noise("10")
    assert mineru_text_is_layout_noise("-10")
    assert mineru_text_is_layout_noise("zhuangyu@cfsc.com.cn")
    assert not mineru_text_is_layout_noise("投资要点")
    assert not mineru_text_is_layout_noise("公司 2025 年全年实现营业收入 388 亿元")


def test_noise_only_merged_text_not_retrievable():
    assert not mineru_merged_text_is_retrievable("0\n10\n20\n30")
    assert mineru_merged_text_is_retrievable("投资要点\n0\n10")


def test_pdf_cover_fragments_merge_or_drop():
    path = "长电科技点评 / 封面"
    segs = [
        _seg("证 券 研 究", start=0, path=path, page=1),
        _seg("报", start=10, path=path, page=1),
        _seg("告", start=11, path=path, page=1),
        _seg("zhuangyu@cfsc.com.cn", start=20, path=path, page=1),
    ]
    merged = merge_mineru_segments_by_section(segs, budget=512, respect_page_boundary=False)
    assert len(merged) <= 1
    if merged:
        assert "证券" in merged[0].text.replace(" ", "") or "@" in merged[0].text


def test_pdf_section_merges_paragraphs():
    path = "研报 / 投资要点 / ▌业绩表现"
    segs = [
        _seg("投资要点", start=0, block="heading", path=path, page=1),
        _seg("▌业绩表现改善", start=20, block="heading", path=path, page=1),
        _seg("当前股价（元） 55.83", start=40, path=path, page=1),
        _seg("公司 2025 年全年实现营业收入 388.71 亿元，同比增长。", start=80, path=path, page=1),
        _seg("续页补充说明。", start=200, path=path, page=2),
    ]
    merged = merge_mineru_segments_by_section(segs, budget=512, respect_page_boundary=False)
    assert len(merged) == 1
    assert "388.71" in merged[0].text
    assert "续页补充" in merged[0].text


def test_pdf_chart_ticks_not_standalone():
    path = "研报 / 投资要点 / 市场表现"
    segs = [
        _seg("市场表现", start=0, block="heading", path=path, page=1),
        _seg("-10", start=10, path=path, page=1),
        _seg("0", start=12, path=path, page=1),
        _seg("10", start=14, path=path, page=1),
        _seg("20", start=16, path=path, page=1),
        _seg("(%) 长电科技 沪深300", start=30, path=path, page=1),
    ]
    merged = merge_mineru_segments_by_section(segs, budget=512, respect_page_boundary=False)
    assert all(len(s.text) > 3 or not mineru_text_is_layout_noise(s.text) for s in merged)
    assert not any(s.text.strip() in {"0", "10", "20", "-10"} for s in merged)


def test_prepare_mineru_prebuilt_pdf_drops_pure_noise():
    segs = [
        _seg("A", start=0, path="节一", page=1),
        _seg("B", start=2, path="节一", page=2),
    ]
    out, log = prepare_mineru_prebuilt_segments(
        segs,
        512,
        parser_type="pdf",
        parser_backend="mineru",
    )
    assert out == []
    assert log and "pdf" in log


def test_prepare_mineru_prebuilt_pdf_merges_cross_page():
    segs = [
        _seg("段落一", start=0, path="节一", page=1),
        _seg("段落二", start=10, path="节一", page=2),
    ]
    out, _ = prepare_mineru_prebuilt_segments(
        segs,
        512,
        parser_type="pdf",
        parser_backend="mineru",
    )
    assert len(out) == 1
    assert "段落一" in out[0].text and "段落二" in out[0].text


def test_pdf_heading_chain_merges_into_following_table():
    table = ParsedSegment(
        text="| 场景 | 设备配置 | 说明 | 备注 |\n| --- | --- | --- | --- |\n| 门诊 | 摄像头 | 说明 | 备注 |",
        start_offset=80,
        end_offset=200,
        page_no=15,
        heading_path="附件2 / 医保智能场景监控终端设备 / 基本配置方案表（参考）",
        metadata={"block": "table", "table_role": "body", "table_index": 0},
    )
    segs = [
        _seg("附件2", start=0, block="heading", path="附件2", page=15),
        _seg(
            "医保智能场景监控终端设备",
            start=10,
            block="heading",
            path="附件2 / 医保智能场景监控终端设备",
            page=15,
        ),
        _seg(
            "基本配置方案表（参考）",
            start=40,
            block="heading",
            path="附件2 / 医保智能场景监控终端设备 / 基本配置方案表（参考）",
            page=15,
        ),
        table,
    ]
    merged = merge_mineru_segments_by_section(segs, budget=1024, respect_page_boundary=False)
    assert len(merged) == 1
    assert "附件2" in merged[0].text
    assert "基本配置方案表（参考）" in merged[0].text
    assert "门诊" in merged[0].text
    assert (merged[0].metadata or {}).get("mineru_context_merged") is True


def test_pdf_consecutive_headings_on_same_page_merge_without_table():
    segs = [
        _seg("附件2", start=0, block="heading", path="附件2", page=15),
        _seg(
            "医保智能场景监控终端设备",
            start=10,
            block="heading",
            path="附件2 / 医保智能场景监控终端设备",
            page=15,
        ),
        _seg("正文段落开始。", start=40, path="附件2 / 医保智能场景监控终端设备", page=15),
    ]
    merged = merge_mineru_segments_by_section(segs, budget=1024, respect_page_boundary=False)
    assert len(merged) == 2
    assert "附件2" in merged[0].text
    assert "医保智能场景监控终端设备" in merged[0].text
    assert "正文段落" in merged[1].text


def test_pdf_attachment_label_and_title_merge_into_table():
    """政务网页 PDF：单独「附件」+ 标题 + 表格应合并为一块。"""
    from app.core.mineru_gateway import MineruResult

    items = [
        {"type": "text", "text": "附件", "text_level": 2, "page_idx": 4},
        {
            "type": "text",
            "text": "医保领域“高效办成一件事”2025 年度第一批重点事项清单",
            "text_level": 2,
            "page_idx": 4,
        },
        {
            "type": "table",
            "page_idx": 4,
            "table_body": "<table><tr><td>序号</td><td>对象</td></tr><tr><td>1</td><td>医药企业</td></tr></table>",
        },
        {
            "type": "text",
            "text": "文件下载链接：国家医疗保障局办公室关于印发《医保领域“高效办成一件事”2025年度第一批重点事项清单》的通知.pdf",
            "page_idx": 4,
        },
    ]
    doc = MineruResult(content_list=items).to_parsed_document()
    merged, _ = prepare_mineru_prebuilt_segments(
        doc.segments, 1024, parser_type="pdf", parser_backend="mineru"
    )
    table_chunks = [s for s in merged if (s.metadata or {}).get("block") == "table"]
    assert len(table_chunks) == 1
    assert "附件" in table_chunks[0].text
    assert "高效办成一件事" in table_chunks[0].text
    assert "序号" in table_chunks[0].text or "| 序号 |" in table_chunks[0].text
    heading_only = [s for s in merged if (s.metadata or {}).get("block") == "heading"]
    assert not any("附件" == s.text.strip() for s in heading_only)
    assert any("文件下载链接" in s.text for s in merged)


def test_pdf_table_with_prefixed_context_drops_orphan_headings():
    """解析阶段已写入表格前缀时，分块阶段应去掉多余标题块。"""
    table = ParsedSegment(
        text=(
            "附件2\n\n医保智能场景监控终端设备\n\n基本配置方案表（参考）\n\n"
            "| 场景 | 设备配置 | 说明 | 备注 |\n| --- | --- | --- | --- |\n| 门诊 | 摄像头 | 说明 | 备注 |"
        ),
        start_offset=80,
        end_offset=200,
        page_no=15,
        heading_path="附件2 / 医保智能场景监控终端设备 / 基本配置方案表（参考）",
        metadata={"block": "table", "table_role": "body", "table_index": 1},
    )
    segs = [
        _seg("附件2", start=0, block="heading", path="附件2", page=15),
        _seg(
            "医保智能场景监控终端设备",
            start=10,
            block="heading",
            path="附件2 / 医保智能场景监控终端设备",
            page=15,
        ),
        _seg(
            "基本配置方案表（参考）",
            start=40,
            block="heading",
            path="附件2 / 医保智能场景监控终端设备 / 基本配置方案表（参考）",
            page=15,
        ),
        table,
    ]
    merged = merge_mineru_segments_by_section(segs, budget=1024, respect_page_boundary=False)
    assert len(merged) == 1
    assert "附件2" in merged[0].text
    assert "门诊" in merged[0].text


def test_law_article_heading_and_enumeration():
    """法条 PDF：节级标题块并入条文，括号枚举项不被逐项切碎。"""
    sec = "第三章 刑罚 / 第一节 刑罚的种类"
    segs = [
        _seg("第三章 刑罚", start=0, block="heading", path="第三章 刑罚", page=5),
        _seg("第一节 刑罚的种类", start=10, block="heading", path=sec, page=5),
        _seg("第三十二条 刑罚分为主刑和附加刑，附加刑也可以独立适用。", start=30, path=sec, page=5),
        _seg("第三十三条 主刑的种类如下：", start=80, path=sec, page=5),
        _seg("（一）管制；", start=110, path=sec, page=5),
        _seg("（二）拘役；", start=120, path=sec, page=5),
        _seg("（三）有期徒刑；", start=130, path=sec, page=5),
        _seg("（四）无期徒刑；", start=145, path=sec, page=5),
    ]
    merged, _ = prepare_mineru_prebuilt_segments(
        segs,
        512,
        parser_type="pdf",
        parser_backend="mineru",
    )
    body = "\n".join(s.text for s in merged)
    assert "第三章 刑罚" in body
    assert "第三十二条" in body
    for item in ("（一）管制", "（二）拘役", "（三）有期徒刑", "（四）无期徒刑"):
        assert item in body
    assert not any(
        (s.metadata or {}).get("block") == "heading"
        and s.text.strip() in {"第三章 刑罚", "第一节 刑罚的种类", "第三章 刑罚\n\n第一节 刑罚的种类"}
        for s in merged
    )
    assert not any(s.text.strip() in {"（一）管制；", "（二）拘役；"} for s in merged)


def test_structured_parser_merge_includes_opendataloader_pdf():
    assert structured_parser_should_merge_sections(parser_type="pdf", parser_backend="opendataloader")
    assert not structured_parser_should_merge_sections(parser_type="docx", parser_backend="opendataloader")


def test_opendataloader_gov_site_fragments_merge():
    """模拟 OpenDataLoader 政策 PDF：页眉/导航/面包屑等短段应合并，表格保持独立。"""
    table = _seg(
        "| 索引号 | 000013874/2024-00001 |\n| --- | --- |",
        start=200,
        block="table",
        page=1,
    )
    table.metadata = {"block": "table", "table_role": "body"}
    segs = [
        _seg("2025年06月01日 星期五 国家医疗保障局", start=0, page=1),
        _seg("首页 时政要闻 机构设置", start=40, block="heading", page=1),
        _seg("当前位置：首页 > 政策法规", start=80, page=1),
        _seg("视力保护色:", start=110, page=1),
        table,
        _seg(
            "国家医疗保障局办公室关于推进基本医保基金即时结算改革的通知",
            start=320,
            block="heading",
            page=1,
        ),
        _seg("各省、自治区、直辖市医疗保障局：", start=360, page=1),
        _seg("为深入贯彻落实党中央、国务院决策部署，推进基本医保基金即时结算改革，现就有关事项通知如下：", start=380, page=1),
    ]
    merged, log = prepare_mineru_prebuilt_segments(
        segs,
        budget=512,
        parser_type="pdf",
        parser_backend="opendataloader",
    )
    assert log and "OpenDataLoader" in log
    assert len(merged) < len(segs)
    assert any((s.metadata or {}).get("block") == "table" or (s.metadata or {}).get("table_role") for s in merged)
    body = "\n".join(s.text for s in merged)
    assert "各省、自治区" in body


def test_odl_layout_noise_patterns():
    assert mineru_text_is_layout_noise("视力保护色:")
    assert mineru_text_is_layout_noise("当前位置：首页 > 政策法规")
    assert mineru_text_is_layout_noise("首页 时政要闻 机构设置")


def test_preamble_includes_document_title_heading():
    title = _seg(
        "国家医疗保障局办公室关于推进基本医保基金即时结算改革的通知",
        start=100,
        block="heading",
        page=1,
    )
    segs = [
        _seg("2025年06月01日 星期五", start=0, page=1),
        _seg("首页 时政要闻", start=30, page=1),
        title,
        _seg("一、总体要求", start=200, block="heading", page=2),
    ]
    merged = merge_leading_preamble_segments(segs)
    assert merged[0].metadata.get("block") == "document_preamble"
    assert "2025年06月01日" in merged[0].text
    assert "即时结算改革" in merged[0].text
    assert merged[1].text.startswith("一、")
