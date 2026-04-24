"""
离线验证 MineruGateway 的 content_list → ParsedDocument 映射是否符合预期。

不依赖真实 MinerU 服务，而是构造典型 content_list（含标题层级、段落、HTML 表格、
Markdown 表格、图片 OCR），断言以下性质：
- 标题按 text_level 归并 heading_path（chapter/section/item 三级）
- 表格拆成「概览 + 行」segments，列名-值结构
- HTML / Markdown 两种 table_body 形态都能解析
- 图片若有 caption/OCR 则进入文本，没有则跳过
- _extract_content_list_and_md 能兼容嵌套 payload

用法：
    cd /root/code/zs-rag/backend
    PYTHONPATH=. python scripts/verify_mineru_mapping.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.mineru_gateway import (  # noqa: E402
    MineruResult,
    _extract_content_list_and_md,
    _html_table_to_rows,
    _markdown_table_to_rows,
    _table_body_to_rows,
)


def _check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  FAIL: {msg}")
        raise SystemExit(1)
    print(f"  ok : {msg}")


def test_html_table() -> None:
    print("[1] HTML 表格解析")
    html = (
        "<table>"
        "<tr><th>列1</th><th>列2</th></tr>"
        "<tr><td>a</td><td>b</td></tr>"
        "<tr><td>c</td><td>d</td></tr>"
        "</table>"
    )
    rows = _html_table_to_rows(html)
    _check(rows == [["列1", "列2"], ["a", "b"], ["c", "d"]], f"行={rows}")


def test_markdown_table() -> None:
    print("[2] Markdown 表格解析")
    md = """
| 列1 | 列2 |
| --- | :---: |
| a  | b  |
| c  | d  |
""".strip()
    rows = _markdown_table_to_rows(md)
    _check(rows == [["列1", "列2"], ["a", "b"], ["c", "d"]], f"行={rows}")


def test_dispatch_table_body() -> None:
    print("[3] table_body 自动分流 HTML / Markdown")
    _check(_table_body_to_rows("<table><tr><td>x</td></tr></table>") == [["x"]], "html 分流")
    _check(_table_body_to_rows("| a | b |\n| - | - |\n| 1 | 2 |") == [["a", "b"], ["1", "2"]], "md 分流")
    _check(_table_body_to_rows("") == [], "空 body")


def test_extract_content_list_shapes() -> None:
    print("[4] _extract_content_list_and_md 兼容多种 payload 结构")
    cl = [{"type": "text", "text": "x"}]
    _check(_extract_content_list_and_md({"content_list": cl, "md_content": "MD"}) == (cl, "MD"), "扁平")
    _check(_extract_content_list_and_md({"doc.pdf": {"content_list": cl}})[0] == cl, "按 filename 嵌套")
    _check(_extract_content_list_and_md({"data": {"content_list": cl}})[0] == cl, "data 包裹")
    _check(_extract_content_list_and_md({"results": [{"content_list": cl}]})[0] == cl, "results 列表")
    _check(_extract_content_list_and_md({"results": {"test": {"content_list": cl}}})[0] == cl, "results 字典")
    import json as _j
    got = _extract_content_list_and_md({"results": {"test": {"content_list": _j.dumps(cl)}}})
    _check(got[0] == cl, f"content_list 为 JSON 字符串也能解析，当前={got[0]}")
    _check(_extract_content_list_and_md({}) == ([], None), "空对象")


def test_to_parsed_document() -> None:
    print("[5] content_list → ParsedDocument 端到端")
    content_list = [
        {"type": "title", "text": "第一章 概述", "text_level": 1, "page_idx": 0},
        {"type": "text", "text": "这是开头段落。", "page_idx": 0},
        {"type": "title", "text": "1.1 背景", "text_level": 2, "page_idx": 0},
        {"type": "list", "text": "要点 A；要点 B；要点 C", "page_idx": 0},
        {
            "type": "table",
            "table_body": (
                "<table>"
                "<tr><th>阶段</th><th>交付物</th></tr>"
                "<tr><td>立项</td><td>方案</td></tr>"
                "<tr><td>开发</td><td>代码</td></tr>"
                "</table>"
            ),
            "table_caption": "表 1 里程碑",
            "page_idx": 1,
        },
        {"type": "title", "text": "第二章 方案", "text_level": 1, "page_idx": 2},
        {
            "type": "table",
            "table_body": "| 环境 | 备注 |\n| --- | --- |\n| dev | 开发 |\n| prod | 生产 |",
            "page_idx": 2,
        },
        {"type": "image", "image_caption": "系统架构图", "img_path": "img_0.png", "page_idx": 2},
        {"type": "image", "img_path": "empty.png", "page_idx": 2},
        {"type": "equation", "text": "E = mc^2", "page_idx": 2},
    ]
    result = MineruResult(
        content_list=content_list,
        markdown="# 第一章\n...",
        source_file_name="demo.pdf",
    )
    doc = result.to_parsed_document()

    _check(doc.parser_type == "mineru", f"parser_type={doc.parser_type}")
    _check(doc.metadata.get("parser_backend") == "mineru", "backend=mineru")
    _check(doc.metadata.get("table_count") == 2, f"表格数={doc.metadata.get('table_count')}")
    _check(doc.metadata.get("heading_count") == 3, f"标题数={doc.metadata.get('heading_count')}")

    headings = [s for s in doc.segments if (s.metadata or {}).get("block") == "heading"]
    _check([h.text for h in headings] == ["第一章 概述", "1.1 背景", "第二章 方案"], "标题顺序")
    _check(
        headings[1].heading_path == "第一章 概述 / 1.1 背景",
        f"二级标题 heading_path={headings[1].heading_path}",
    )
    _check(
        headings[2].heading_path == "第二章 方案",
        f"新一级标题应重置栈，当前={headings[2].heading_path}",
    )

    paragraphs_in_c1 = [
        s for s in doc.segments
        if (s.metadata or {}).get("block") == "paragraph" and s.heading_path == "第一章 概述"
    ]
    _check(any("开头段落" in s.text for s in paragraphs_in_c1), "开头段落归到第一章")

    list_seg = [
        s for s in doc.segments
        if (s.metadata or {}).get("list") is True
    ]
    _check(
        len(list_seg) == 1 and list_seg[0].heading_path == "第一章 概述 / 1.1 背景",
        "列表段落归到 1.1 背景",
    )

    table_overviews = [
        s for s in doc.segments
        if (s.metadata or {}).get("table_role") == "overview"
    ]
    _check(len(table_overviews) == 2, f"两个表格概览，当前={len(table_overviews)}")
    _check(
        "阶段" in table_overviews[0].text and "交付物" in table_overviews[0].text,
        f"表1概览含表头，{table_overviews[0].text}",
    )
    _check(
        table_overviews[0].heading_path == "第一章 概述 / 1.1 背景",
        f"表1 heading_path={table_overviews[0].heading_path}",
    )
    _check(
        table_overviews[1].heading_path == "第二章 方案",
        f"表2 heading_path={table_overviews[1].heading_path}",
    )

    table_rows = [
        s for s in doc.segments
        if (s.metadata or {}).get("table_role") == "row"
    ]
    _check(len(table_rows) == 4, f"两张表合计 4 行，当前={len(table_rows)}")
    _check(
        any("阶段：立项；交付物：方案" == s.text for s in table_rows),
        "行文本形如「列名：值；列名：值」",
    )

    table_caption = [s for s in doc.segments if (s.metadata or {}).get("table_role") == "caption"]
    _check(len(table_caption) == 1 and "表 1 里程碑" in table_caption[0].text, "表格 caption 作为独立段落")

    images = [s for s in doc.segments if (s.metadata or {}).get("block") == "image"]
    _check(
        len(images) == 1 and "系统架构图" in images[0].text,
        f"仅有 caption 的图片才入段，当前={[i.text for i in images]}",
    )

    eq = [s for s in doc.segments if (s.metadata or {}).get("equation") is True]
    _check(len(eq) == 1 and "E = mc^2" in eq[0].text, "公式段保留")

    table_segment = table_overviews[0]
    _check(table_segment.page_no == 2, f"table page_no 来自 page_idx+1，当前={table_segment.page_no}")

    _check(doc.char_count > 0, f"char_count={doc.char_count}")
    for seg in doc.segments:
        _check(
            doc.text[seg.start_offset:seg.end_offset] == seg.text,
            f"offset 对齐: {seg.text[:30]}",
        )


def main() -> None:
    test_html_table()
    test_markdown_table()
    test_dispatch_table_body()
    test_extract_content_list_shapes()
    test_to_parsed_document()
    print("\nALL PASSED")


if __name__ == "__main__":
    main()
