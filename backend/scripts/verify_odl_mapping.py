"""
离线验证 OpenDataLoader JSON kids → ParsedDocument / content_list 映射。

不依赖 Java / opendataloader-pdf 运行时，使用构造的 ODL JSON 样例。

用法：
    cd /root/code/zs-rag/backend
    PYTHONPATH=. python scripts/verify_odl_mapping.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.opendataloader_gateway import (  # noqa: E402
    OpenDataLoaderResult,
    _bbox_odl_to_mineru,
    resolve_pdf_parser,
)


def _check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  FAIL: {msg}")
        raise SystemExit(1)
    print(f"  ok : {msg}")


def test_bbox_flip() -> None:
    print("[1] bbox ODL → MinerU 坐标翻转")
    # ODL: [left, bottom, right, top] on 792pt page
    flipped = _bbox_odl_to_mineru([72.0, 400.0, 540.0, 650.0], 792.0)
    _check(flipped is not None, f"flipped={flipped}")
    _check(flipped[0] == 72.0 and flipped[2] == 540.0, "x 不变")
    _check(flipped[1] < flipped[3], "y0 < y1（左上原点）")


def test_resolve_pdf_parser() -> None:
    print("[2] resolve_pdf_parser 优先级")
    _check(resolve_pdf_parser({"pdf_parser": "mineru"}) == "mineru", "kb mineru")
    _check(resolve_pdf_parser({"pdf_parser": "opendataloader"}) == "opendataloader", "kb odl")
    _check(resolve_pdf_parser(None) in {"opendataloader", "mineru", "pypdf"}, "全局默认")


def test_to_parsed_document() -> None:
    print("[3] ODL JSON → ParsedDocument / content_list")
    doc_json = {
        "file name": "demo.pdf",
        "page height": 792,
        "kids": [
            {
                "type": "heading",
                "heading level": 1,
                "content": "第一章 概述",
                "page number": 1,
                "bounding box": [72.0, 700.0, 400.0, 720.0],
            },
            {
                "type": "paragraph",
                "content": "这是正文段落。",
                "page number": 1,
                "bounding box": [72.0, 620.0, 500.0, 680.0],
            },
            {
                "type": "table",
                "content": "| 列1 | 列2 |\n| --- | --- |\n| a | b |",
                "page number": 2,
                "bounding box": [72.0, 200.0, 500.0, 400.0],
            },
            {
                "type": "picture",
                "description": "系统架构图",
                "page number": 2,
            },
        ],
    }
    result = OpenDataLoaderResult(
        doc_json=doc_json,
        markdown="# 第一章 概述\n\n这是正文段落。",
        source_file_name="demo.pdf",
        page_heights={1: 792.0, 2: 792.0},
    )
    cl = result.to_content_list()
    _check(len(cl) >= 3, f"content_list 条数={len(cl)}")
    _check(cl[0].get("type") in {"title", "text"}, "标题映射")
    _check(all("page_idx" in x for x in cl if x.get("type") != "image"), "page_idx 存在")
    _check(all("bbox" in x for x in cl[:2]), "bbox 存在")

    doc = result.to_parsed_document()
    _check(doc.char_count > 0, f"char_count={doc.char_count}")
    _check(len(doc.segments) >= 3, f"segments={len(doc.segments)}")
    _check(doc.metadata.get("parser_backend") == "opendataloader", "parser_backend")
    _check(doc.metadata.get("table_count", 0) >= 1, "table_count")


def test_odl_rows_table() -> None:
    print("[4] ODL rows/cells → table_body / HTML")
    doc_json = {
        "file name": "rows.pdf",
        "page height": 792,
        "kids": [
            {
                "type": "table",
                "page number": 1,
                "bounding box": [72.0, 200.0, 500.0, 400.0],
                "rows": [
                    {
                        "type": "table row",
                        "row number": 1,
                        "cells": [
                            {"type": "table cell", "row number": 1, "column number": 1, "content": "股票简称"},
                            {"type": "table cell", "row number": 1, "column number": 2, "content": "EPS"},
                        ],
                    },
                    {
                        "type": "table row",
                        "row number": 2,
                        "cells": [
                            {"type": "table cell", "row number": 2, "column number": 1, "content": "平高电气"},
                            {"type": "table cell", "row number": 2, "column number": 2, "content": "1.00"},
                        ],
                    },
                ],
            }
        ],
    }
    result = OpenDataLoaderResult(
        doc_json=doc_json,
        markdown=None,
        source_file_name="rows.pdf",
        page_heights={1: 792.0},
    )
    cl = result.to_content_list()
    tables = [x for x in cl if x.get("type") == "table"]
    _check(len(tables) == 1, "rows table 映射")
    body = tables[0].get("table_body") or ""
    _check("平高电气" in body and "股票简称" in body, f"table_body 含单元格 body_len={len(body)}")
    doc = result.to_parsed_document()
    overview = next(s for s in doc.segments if (s.metadata or {}).get("table_role") == "overview")
    _check("table_body_html" in (overview.metadata or {}), "overview 含 table_body_html")


def main() -> None:
    test_bbox_flip()
    test_resolve_pdf_parser()
    test_to_parsed_document()
    test_odl_rows_table()
    print("\n全部通过。")


if __name__ == "__main__":
    main()
