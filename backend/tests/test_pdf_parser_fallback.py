"""PDF 解析器降级链与可用性检测。"""

from unittest.mock import MagicMock, patch

from app.core.document_parser import (
    ParsedDocument,
    ParsedSegment,
    _pdf_parse_usable,
    _pypdf_parse_suspicious,
    parse_document,
)
from app.core.parser_config import ParserOptions, resolve_pdf_fallback_chain


def test_resolve_pdf_fallback_chain_primary_opendataloader():
    with patch("app.core.config.get_settings") as gs:
        s = MagicMock()
        s.mineru_enabled = True
        s.odl_enabled = True
        gs.return_value = s
        chain = resolve_pdf_fallback_chain("opendataloader")
    assert chain == ["opendataloader", "mineru", "pypdf"]


def test_resolve_pdf_fallback_chain_primary_mineru():
    with patch("app.core.config.get_settings") as gs:
        s = MagicMock()
        s.mineru_enabled = True
        s.odl_enabled = True
        gs.return_value = s
        chain = resolve_pdf_fallback_chain("mineru")
    assert chain[0] == "mineru"
    assert "opendataloader" in chain
    assert chain[-1] == "pypdf"


def test_pdf_parse_usable_rejects_image_only_odl():
    segs = [
        ParsedSegment(text="![Image](x)", start_offset=0, end_offset=12, metadata={"block": "image"}),
        ParsedSegment(text="![Image](y)", start_offset=13, end_offset=25, metadata={"block": "image"}),
    ]
    doc = ParsedDocument(
        parser_type="pdf",
        text="![Image](x)\n![Image](y)",
        char_count=24,
        segments=segs,
        metadata={"parser_backend": "opendataloader"},
    )
    assert _pdf_parse_usable(doc) is False


def test_pdf_parse_usable_rejects_odl_zero_segments_with_markdown():
    """ODL 扫描件：有 Markdown 字符数但 0 分段、0 content_list → 应触发降级。"""
    md = "\n".join(f"![Image](page{i}.jpg)" for i in range(16))
    doc = ParsedDocument(
        parser_type="pdf",
        text=md,
        char_count=len(md),
        segments=[],
        metadata={
            "parser_backend": "opendataloader",
            "content_list_length": 0,
            "heading_count": 0,
            "table_count": 0,
        },
    )
    assert _pdf_parse_usable(doc) is False


def test_pdf_parse_usable_accepts_mineru_text():
    text = "这是一段足够长的正文内容用于索引"
    doc = ParsedDocument(
        parser_type="pdf",
        text=text,
        char_count=len(text),
        segments=[
            ParsedSegment(text=text, start_offset=0, end_offset=len(text), metadata={"block": "paragraph"}),
        ],
        metadata={"parser_backend": "mineru"},
    )
    assert _pdf_parse_usable(doc) is True


def test_pypdf_parse_suspicious_rejects_huge_garbage():
    garbage = "x" * 100_000
    doc = ParsedDocument(
        parser_type="pdf",
        text=garbage,
        char_count=len(garbage),
        segments=[ParsedSegment(text=garbage, start_offset=0, end_offset=len(garbage))],
        metadata={"parser_backend": "pypdf_fallback", "fallback": True},
    )
    assert _pypdf_parse_suspicious(doc) is True
    assert _pdf_parse_usable(doc) is False


def test_odl_unusable_falls_back_to_mineru():
    md = "\n".join(f"![Image](page{i}.jpg)" for i in range(16))
    odl_doc = ParsedDocument(
        parser_type="pdf",
        text=md,
        char_count=len(md),
        segments=[],
        metadata={
            "parser_backend": "opendataloader",
            "content_list_length": 0,
            "heading_count": 0,
            "table_count": 0,
        },
    )
    mineru_result = MagicMock()
    mineru_result.markdown = "# ok"
    mineru_result.content_list = [{"type": "text", "text": "有效正文内容超过十二字", "page_idx": 0}]
    mineru_text = "这是一段足够长的 MinerU 正文内容"
    mineru_result.to_parsed_document.return_value = ParsedDocument(
        parser_type="mineru",
        text=mineru_text,
        char_count=len(mineru_text),
        segments=[
            ParsedSegment(
                text=mineru_text,
                start_offset=0,
                end_offset=len(mineru_text),
                metadata={"block": "paragraph", "parser_backend": "mineru"},
            )
        ],
        metadata={"parser_backend": "mineru", "heading_count": 0, "table_count": 0},
    )

    odl_result = MagicMock()
    odl_result.markdown = ""
    odl_result.to_parsed_document.return_value = odl_doc
    odl_result.to_content_list.return_value = []

    mock_odl = MagicMock()
    mock_odl.is_enabled.return_value = True
    mock_odl.parse.return_value = odl_result

    mock_gw = MagicMock()
    mock_gw.is_enabled.return_value = True
    mock_gw.should_handle.return_value = True
    mock_gw.backend = "pipeline"
    mock_gw.lang = "ch"
    mock_gw.parse.return_value = mineru_result

    opts = ParserOptions(
        pdf_engine="opendataloader",
        pdf_hybrid=False,
        docx_engine="python-docx",
        excel_engine="html_table",
        csv_engine="standard",
        text_engine="native",
    )

    logs: list[str] = []

    with (
        patch("app.core.config.get_settings") as gs,
        patch("app.core.opendataloader_gateway.get_opendataloader_gateway", return_value=mock_odl),
        patch("app.core.mineru_gateway.get_mineru_gateway", return_value=mock_gw),
    ):
        settings = MagicMock()
        settings.mineru_enabled = True
        settings.odl_enabled = True
        gs.return_value = settings
        doc = parse_document("scan.pdf", b"%PDF", log=logs.append, parser_options=opts)

    assert doc.metadata.get("parser_backend") == "mineru"
    assert doc.metadata.get("parser_fallback") is True
    assert any("降级" in line for line in logs)
