"""MinerU 内嵌图 OCR 与空 caption 处理。"""

from app.core.mineru_gateway import (
    MineruResult,
    _image_caption_text,
    _image_needs_ocr,
    _image_ocr_text,
    _mineru_safe_upload_filename,
    _plain_text,
)


def test_mineru_safe_upload_filename_strips_problematic_chars():
    raw = "长电科技(600584)：盈利能力复苏.pdf"
    safe = _mineru_safe_upload_filename(raw)
    assert "(" not in safe and ")" not in safe and "：" not in safe
    assert safe.endswith(".pdf")
    assert safe.isascii()
    assert safe.startswith("doc_") or "600584" in safe


def test_mineru_safe_upload_filename_pure_cjk_uses_hash():
    raw = "长电科技：盈利能力复苏.pdf"
    safe = _mineru_safe_upload_filename(raw)
    assert safe.isascii()
    assert safe.startswith("doc_")
    assert safe.endswith(".pdf")


def test_plain_text_empty_list_not_brackets():
    assert _plain_text([]) == ""
    assert _plain_text(["图1", "说明"]) == "图1 说明"


def test_image_caption_empty_list():
    item = {"type": "image", "image_caption": [], "img_path": "images/a.png"}
    assert _image_caption_text(item) == ""
    assert _image_needs_ocr(item) is True


def test_image_segment_skips_empty_caption():
    result = MineruResult(
        content_list=[
            {"type": "text", "text": "步骤说明", "page_idx": 0},
            {"type": "image", "image_caption": [], "img_path": "images/a.png", "page_idx": 0},
        ],
        markdown="# 步骤说明",
        source_file_name="a.docx",
    )
    doc = result.to_parsed_document()
    assert len(doc.segments) == 1
    assert doc.segments[0].text == "步骤说明"


def test_image_segment_includes_ocr_text():
    result = MineruResult(
        content_list=[
            {
                "type": "image",
                "image_caption": [],
                "image_ocr_text": "豫事办 推荐服务 新生儿出生",
                "img_path": "images/a.png",
                "page_idx": 0,
            },
        ],
        markdown="",
        source_file_name="a.docx",
    )
    doc = result.to_parsed_document()
    assert len(doc.segments) == 1
    assert "新生儿出生" in doc.segments[0].text
    assert _image_ocr_text(result.content_list[0]) == "豫事办 推荐服务 新生儿出生"
