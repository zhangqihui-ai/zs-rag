"""Word（docx）解析视图导出：content_list / Markdown，供前端 Markdown·JSON·表格 Tab 与块级联动。"""

from __future__ import annotations

import html as html_module
import json
from typing import Any

from app.core.document_parser import ParsedSegment

DOCX_VIEW_MD_FILENAME = "docx_markdown.md"
DOCX_VIEW_CL_FILENAME = "docx_content_list.json"


def assign_docx_block_indices(segments: list[ParsedSegment]) -> None:
    """为每个 segment 写入 metadata.block_index（0-based，与 content_list 下标一致）。"""
    for i, seg in enumerate(segments):
        meta = dict(seg.metadata or {})
        meta["block_index"] = i
        seg.metadata = meta


def sync_docx_page_metadata(segments: list[ParsedSegment]) -> None:
    """将 parser 写入的 page_no 同步到 metadata.page_idx（供 content_list / 前端分页）。"""
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        meta = dict(seg.metadata or {})
        page_no = seg.page_no if seg.page_no is not None else meta.get("page_no")
        if page_no is None:
            page_no = 1
            seg.page_no = 1
        try:
            pn = max(1, int(page_no))
        except (TypeError, ValueError):
            pn = 1
        meta["page_no"] = pn
        meta["page_idx"] = pn - 1
        seg.page_no = pn
        seg.metadata = meta


def _segment_type(seg: ParsedSegment) -> str:
    meta = seg.metadata or {}
    block = meta.get("block")
    if block == "heading":
        cls = str(meta.get("heading_class") or "")
        if cls == "chapter":
            return "title"
        if cls == "section":
            return "section"
        return "title"
    if block == "table":
        role = meta.get("table_role")
        if role == "overview":
            return "table_overview"
        return "table"
    return "text"


def _heading_markdown_prefix(seg: ParsedSegment) -> str:
    meta = seg.metadata or {}
    cls = str(meta.get("heading_class") or "")
    if cls == "chapter":
        return "## "
    if cls == "section":
        return "### "
    return "#### "


def build_docx_content_list(segments: list[ParsedSegment]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for i, seg in enumerate(segments):
        meta = dict(seg.metadata or {})
        text = seg.text.strip()
        if not text:
            continue
        item: dict[str, Any] = {
            "block_index": i,
            "type": _segment_type(seg),
            "text": text,
            "block": meta.get("block"),
            "heading_path": seg.heading_path,
        }
        if meta.get("heading_class"):
            item["heading_class"] = meta.get("heading_class")
        if meta.get("table_role"):
            item["table_role"] = meta.get("table_role")
        if meta.get("table_index") is not None:
            item["table_index"] = meta.get("table_index")
        if meta.get("page_idx") is not None:
            item["page_idx"] = meta.get("page_idx")
        if meta.get("page_no") is not None:
            item["page_no"] = meta.get("page_no")
        items.append(item)
    return items


def _segment_markdown_line(seg: ParsedSegment) -> str | None:
    text = seg.text.strip()
    if not text:
        return None
    meta = seg.metadata or {}
    block = meta.get("block")
    if block == "heading":
        return f"{_heading_markdown_prefix(seg)}{text}"
    if block == "table" and meta.get("table_role") == "row" and "\n" in text:
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
        return "\n".join(f"- {ln}" for ln in lines)
    return text


def build_docx_markdown(segments: list[ParsedSegment]) -> str:
    parts: list[str] = []
    current_page: int | None = None
    for seg in segments:
        line = _segment_markdown_line(seg)
        if not line:
            continue
        meta = seg.metadata or {}
        page_idx = int(meta.get("page_idx") or 0)
        if current_page is None or page_idx != current_page:
            if parts:
                parts.append("")
            parts.append(f"[第{page_idx + 1}页]")
            parts.append("")
            current_page = page_idx
        parts.append(line)
    return "\n\n".join(parts).strip() + ("\n" if parts else "")


def table_blocks_from_content_list(content_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for item in content_list
        if str(item.get("type") or "").startswith("table") or item.get("block") == "table"
    ]


def rows_to_preview_html(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    parts = ["<table>"]
    for ri, row in enumerate(rows):
        parts.append("<tr>")
        tag = "th" if ri == 0 else "td"
        for cell in row:
            parts.append(f"<{tag}>{html_module.escape(str(cell))}</{tag}>")
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)


def table_block_preview_html(item: dict[str, Any]) -> str:
    """将表格类 block 的文本转为简易 HTML 表格（用于前端表格 Tab）。"""
    text = str(item.get("text") or "").strip()
    if not text:
        return ""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return f"<p>{html_module.escape(text)}</p>"
    rows: list[list[str]] = []
    for line in lines:
        if "；" in line and "：" in line:
            cells = []
            for part in line.split("；"):
                idx = part.find("：")
                if idx > 0:
                    cells.append(part[idx + 1 :].strip())
                elif part.strip():
                    cells.append(part.strip())
            if cells:
                rows.append(cells)
                continue
        if "|" in line:
            rows.append([c.strip() for c in line.split("|") if c.strip()])
        else:
            rows.append([line])
    if len(rows) >= 2:
        return rows_to_preview_html(rows)
    return f"<pre>{html_module.escape(text)}</pre>"


def persist_docx_view_artifacts(*, segments: list[ParsedSegment], file_path_parent) -> dict[str, bool]:
    """落盘 docx Markdown / content_list，返回 parse_view 标志。"""
    from pathlib import Path

    parent = Path(file_path_parent)
    assign_docx_block_indices(segments)
    sync_docx_page_metadata(segments)
    content_list = build_docx_content_list(segments)
    markdown = build_docx_markdown(segments)
    view: dict[str, bool] = {"markdown": False, "content_list": False, "tables": False}
    if markdown.strip():
        (parent / DOCX_VIEW_MD_FILENAME).write_text(markdown, encoding="utf-8")
        view["markdown"] = True
    if content_list:
        (parent / DOCX_VIEW_CL_FILENAME).write_text(
            json.dumps(content_list, ensure_ascii=False),
            encoding="utf-8",
        )
        view["content_list"] = True
        view["tables"] = len(table_blocks_from_content_list(content_list)) > 0
    return view
