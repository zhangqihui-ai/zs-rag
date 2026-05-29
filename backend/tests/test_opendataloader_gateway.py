"""OpenDataLoader gateway hybrid 参数与映射单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.opendataloader_gateway import OpenDataLoaderGateway, reset_opendataloader_gateway


@pytest.fixture(autouse=True)
def _reset_gateway():
    reset_opendataloader_gateway()
    yield
    reset_opendataloader_gateway()


def test_hybrid_parse_passes_full_mode_and_sidecar_url(tmp_path):
    gw = OpenDataLoaderGateway(
        enabled=True,
        hybrid=False,
        hybrid_url="http://opendataloader-hybrid:5002",
        timeout=120,
    )
    pdf_bytes = b"%PDF-1.4 minimal"
    captured: dict = {}

    def fake_convert(**kwargs):
        captured.update(kwargs)
        out_dir = kwargs["output_dir"]
        stem = "doc"
        json_path = tmp_path / "out" / f"{stem}.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            '{"kids":[{"type":"page","page number":1,"kids":[{"type":"paragraph","content":"OCR text"}]}]}',
            encoding="utf-8",
        )
        (tmp_path / "out" / f"{stem}.md").write_text("# OCR text", encoding="utf-8")

    with patch("opendataloader_pdf.convert", side_effect=fake_convert):
        with patch("app.core.opendataloader_gateway._java_available", return_value=True):
            with patch("tempfile.TemporaryDirectory") as tmpdir:
                tmpdir.return_value.__enter__.return_value = str(tmp_path)
                result = gw.parse(pdf_bytes, "doc.pdf", use_hybrid=True)

    assert captured.get("hybrid") == "docling-fast"
    assert captured.get("hybrid_mode") == "full"
    assert captured.get("hybrid_url") == "http://opendataloader-hybrid:5002"
    assert captured.get("hybrid_timeout") == "120000"
    assert captured.get("hybrid_fallback") is True
    doc = result.to_parsed_document()
    assert doc.char_count > 0
    assert len(doc.segments) >= 1
