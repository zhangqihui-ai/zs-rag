"""
OpenDataLoader PDF Python SDK 集成 + JSON kids → ParsedDocument / content_list 映射。

PDF 解析底层为 Java（opendataloader-pdf 通过 subprocess 调 JVM），业务层仍为 Python。
"""

from __future__ import annotations

import json
import html as html_module
import logging
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.heading_match import normalize_heading_match_text
from app.core.document_parser import (
    ParsedDocument,
    ParsedSegment,
    _CLASS_ORDER,
    _update_heading_path,
    build_table_segments_from_rows,
    build_table_segments_smart,
)
from app.core.mineru_gateway import (
    _append_segment,
    _grid_to_html_table,
    _grid_to_markdown_table,
    _markdown_table_to_rows,
    _plain_text,
    _preserve_newlines,
    _table_body_to_rows,
    _text_level_to_class,
)

logger = logging.getLogger(__name__)

# ODL JSON 常用页高（pt），用于 bbox Y 轴翻转；优先用文档/页级 height
_DEFAULT_PAGE_HEIGHT = 792.0

_PDF_PARSER_BACKENDS = frozenset({"opendataloader", "mineru", "docling"})


class OpenDataLoaderUnavailableError(Exception):
    """OpenDataLoader 未启用、Java 不可用或 convert 失败。"""


def resolve_pdf_parser(kb_config: dict[str, Any] | None) -> str:
    """知识库 config.pdf_parser > 全局 ODL 默认 > mineru > pypdf。"""
    if isinstance(kb_config, dict):
        raw = kb_config.get("pdf_parser")
        if isinstance(raw, str) and raw.strip():
            parser = raw.strip().lower()
            if parser in _PDF_PARSER_BACKENDS or parser == "pypdf":
                return parser
    settings = get_settings()
    if settings.odl_enabled:
        return settings.odl_default_parser
    if settings.mineru_enabled:
        return "mineru"
    return "pypdf"


def resolve_pdf_parser_hybrid(kb_config: dict[str, Any] | None) -> bool:
    if isinstance(kb_config, dict) and kb_config.get("pdf_parser_hybrid") is True:
        return True
    return get_settings().odl_hybrid


def _java_available() -> bool:
    java = shutil.which("java")
    if not java:
        return False
    try:
        proc = subprocess.run(
            [java, "-version"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        return proc.returncode == 0 or bool(proc.stderr or proc.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return False


def _get_field(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    return None


def _element_page_number(item: dict[str, Any]) -> int | None:
    raw = _get_field(item, "page number", "page_number", "pageNumber", "page")
    if isinstance(raw, int) and raw >= 1:
        return raw
    if isinstance(raw, float) and raw >= 1:
        return int(raw)
    return None


def _element_bbox_raw(item: dict[str, Any]) -> list[float] | None:
    raw = _get_field(item, "bounding box", "bounding_box", "bbox")
    if not isinstance(raw, list) or len(raw) < 4:
        return None
    try:
        return [float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3])]
    except (TypeError, ValueError):
        return None


def _bbox_odl_to_mineru(bbox: list[float] | None, page_height: float) -> list[float] | None:
    """ODL [left, bottom, right, top]（PDF 左下原点）→ MinerU/UI [x0, y0, x1, y1]（左上原点）。"""
    if bbox is None or page_height <= 0:
        return None
    left, bottom, right, top = bbox[0], bbox[1], bbox[2], bbox[3]
    y0 = page_height - top
    y1 = page_height - bottom
    if y0 > y1:
        y0, y1 = y1, y0
    return [left, y0, right, y1]


def _heading_level(item: dict[str, Any]) -> int | None:
    raw = _get_field(item, "heading level", "heading_level", "level", "text_level")
    if isinstance(raw, int) and raw >= 1:
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def _element_content(item: dict[str, Any]) -> str:
    typ = str(item.get("type") or "").lower()
    if typ == "code":
        return _preserve_newlines(_get_field(item, "content", "text", "code_body"))
    content = _get_field(item, "content", "text")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [_element_content(k) if isinstance(k, dict) else str(k) for k in content]
        return "\n".join(p for p in parts if p).strip()
    return ""


def _odl_cell_text(cell: dict[str, Any]) -> str:
    if not isinstance(cell, dict):
        return _plain_text(str(cell))
    content = _get_field(cell, "content", "text")
    if isinstance(content, str) and content.strip():
        return _plain_text(content)
    kids = cell.get("kids")
    if isinstance(kids, list):
        parts: list[str] = []
        for kid in kids:
            if isinstance(kid, dict):
                text = _element_content(kid)
                if text:
                    parts.append(text)
        if parts:
            return _plain_text(" ".join(parts))
    return ""


def _odl_table_rows_grid(item: dict[str, Any]) -> list[list[str]]:
    """从 ODL JSON 的 rows/cells 提取二维文本网格。"""
    rows_field = item.get("rows")
    if not isinstance(rows_field, list):
        return []
    grid: list[list[str]] = []
    for row in rows_field:
        if not isinstance(row, dict):
            continue
        cells = row.get("cells")
        if not isinstance(cells, list):
            continue
        row_cells = [_odl_cell_text(c) if isinstance(c, dict) else _plain_text(str(c)) for c in cells]
        if any(c.strip() for c in row_cells):
            grid.append(row_cells)
    return grid


def _odl_table_to_html(item: dict[str, Any]) -> str:
    """从 ODL table 节点（含 rowspan/colspan）生成 HTML。"""
    rows_field = item.get("rows")
    if not isinstance(rows_field, list) or not rows_field:
        return ""
    parts = ["<table>"]
    for row in rows_field:
        if not isinstance(row, dict):
            continue
        cells = row.get("cells")
        if not isinstance(cells, list):
            continue
        parts.append("<tr>")
        for cell in cells:
            if not isinstance(cell, dict):
                continue
            text = _odl_cell_text(cell)
            row_span = int(_get_field(cell, "row span", "rowspan") or 1)
            col_span = int(_get_field(cell, "column span", "colspan") or 1)
            attrs = ""
            if row_span > 1:
                attrs += f' rowspan="{row_span}"'
            if col_span > 1:
                attrs += f' colspan="{col_span}"'
            row_no = _get_field(cell, "row number", "row_number")
            tag = "th" if isinstance(row_no, int) and row_no <= 2 else "td"
            parts.append(f"<{tag}{attrs}>{html_module.escape(text)}</{tag}>")
        parts.append("</tr>")
    parts.append("</table>")
    html = "".join(parts)
    return html if _odl_table_rows_grid(item) else ""


def _table_body_from_odl(item: dict[str, Any]) -> str:
    body = _get_field(item, "content", "table_body", "html", "markdown")
    if isinstance(body, str) and body.strip():
        return body.strip()
    html = _odl_table_to_html(item)
    if html:
        return html
    grid = _odl_table_rows_grid(item)
    if grid:
        md = _grid_to_markdown_table(grid)
        if md:
            return md
    kids = item.get("kids")
    if not isinstance(kids, list):
        return ""
    rows_md: list[str] = []
    for kid in kids:
        if not isinstance(kid, dict):
            continue
        row_type = str(kid.get("type") or "").lower()
        if row_type not in {"row", "table_row", "tr"}:
            cell_text = _element_content(kid)
            if cell_text:
                rows_md.append(cell_text)
            continue
        cells = kid.get("kids") or kid.get("cells") or []
        if not isinstance(cells, list):
            continue
        cell_texts: list[str] = []
        for cell in cells:
            if isinstance(cell, dict):
                cell_texts.append(_plain_text(_element_content(cell)))
            else:
                cell_texts.append(_plain_text(str(cell)))
        if cell_texts:
            rows_md.append("| " + " | ".join(cell_texts) + " |")
    if not rows_md:
        return ""
    if len(rows_md) >= 2 and not rows_md[1].startswith("| ---"):
        sep = "| " + " | ".join("---" for _ in rows_md[0].split("|")[1:-1]) + " |"
        rows_md.insert(1, sep)
    return "\n".join(rows_md)


def _iter_odl_elements(doc: dict[str, Any]) -> list[dict[str, Any]]:
    kids = doc.get("kids")
    if not isinstance(kids, list):
        return []
    out: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        typ = str(node.get("type") or "").lower()
        if typ and typ not in {"document", "page"}:
            out.append(node)
        children = node.get("kids")
        if isinstance(children, list):
            for child in children:
                walk(child)

    for kid in kids:
        walk(kid)
    return out


def _page_heights_from_doc(doc: dict[str, Any]) -> dict[int, float]:
    heights: dict[int, float] = {}
    default_h = _get_field(doc, "page height", "page_height")
    if isinstance(default_h, (int, float)) and default_h > 0:
        default_val = float(default_h)
    else:
        default_val = _DEFAULT_PAGE_HEIGHT

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if str(node.get("type") or "").lower() == "page":
            pn = _element_page_number(node)
            ph = _get_field(node, "height", "page height", "page_height")
            if pn is not None:
                if isinstance(ph, (int, float)) and ph > 0:
                    heights[pn] = float(ph)
                elif pn not in heights:
                    heights[pn] = default_val
        children = node.get("kids")
        if isinstance(children, list):
            for child in children:
                walk(child)

    kids = doc.get("kids")
    if isinstance(kids, list):
        for kid in kids:
            walk(kid)
    return heights


def _odl_type_to_content_list_type(typ: str, heading_level: int | None) -> tuple[str, int | None]:
    t = typ.lower()
    if t == "heading":
        lvl = heading_level or 1
        if lvl <= 1:
            return "title", lvl
        return "text", lvl
    if t in {"paragraph", "list", "caption", "footnote"}:
        return "text" if t == "paragraph" else t, None
    if t == "table":
        return "table", None
    if t in {"picture", "image", "figure"}:
        return "image", None
    if t == "equation":
        return "equation", None
    if t == "code":
        return "code", None
    return "text", None


@dataclass
class OpenDataLoaderResult:
    doc_json: dict[str, Any]
    markdown: str | None
    source_file_name: str
    page_heights: dict[int, float] = field(default_factory=dict)

    def to_content_list(self) -> list[dict[str, Any]]:
        content_list: list[dict[str, Any]] = []
        for item in _iter_odl_elements(self.doc_json):
            typ = str(item.get("type") or "").lower()
            if typ in {"header", "footer", "page_number", "watermark"}:
                continue
            page_no = _element_page_number(item)
            page_idx = (page_no - 1) if page_no is not None else None
            page_h = self.page_heights.get(page_no or 0, _DEFAULT_PAGE_HEIGHT)
            bbox = _bbox_odl_to_mineru(_element_bbox_raw(item), page_h)
            hl = _heading_level(item)
            cl_type, text_level = _odl_type_to_content_list_type(typ, hl)

            entry: dict[str, Any] = {"type": cl_type}
            if page_idx is not None:
                entry["page_idx"] = page_idx
            if bbox is not None:
                entry["bbox"] = bbox
            if text_level is not None:
                entry["text_level"] = text_level

            if cl_type == "table":
                body = _table_body_from_odl(item)
                if body:
                    entry["table_body"] = body
                caption = _plain_text(_get_field(item, "caption", "table_caption"))
                if caption:
                    entry["table_caption"] = caption
            elif cl_type == "image":
                desc = _plain_text(_get_field(item, "description", "alt", "caption", "image_caption"))
                if desc:
                    entry["image_caption"] = desc
                img_path = _get_field(item, "image path", "image_path", "img_path")
                if isinstance(img_path, str):
                    entry["img_path"] = img_path
            elif cl_type == "code":
                entry["code_body"] = _element_content(item)
            else:
                text = _element_content(item)
                if text:
                    entry["text"] = text

            if cl_type == "image" and not entry.get("image_caption") and not entry.get("img_path"):
                continue
            if cl_type != "table" and cl_type != "image" and not _plain_text(entry.get("text") or entry.get("code_body") or ""):
                if bbox is None:
                    continue
            content_list.append(entry)
        return content_list

    def to_parsed_document(self) -> ParsedDocument:
        content_list = self.to_content_list()
        segments: list[ParsedSegment] = []
        parts: list[str] = []
        offset_ref = [0]
        heading_stack: list[tuple[str, str]] = []
        current_heading_path: str | None = None
        table_counter = 0
        heading_count = 0

        for cl_index, item in enumerate(content_list):
            typ = str(item.get("type") or "").lower()
            page_idx = item.get("page_idx")
            page_no = (page_idx + 1) if isinstance(page_idx, int) else None
            bbox = item.get("bbox") if isinstance(item.get("bbox"), list) else None
            text_level = item.get("text_level")

            if typ in {"header", "footer", "page_number"}:
                continue

            is_heading = typ == "title" or (typ == "text" and text_level)
            if is_heading:
                text = _plain_text(item.get("text") or item.get("content"))
                if not text:
                    continue
                cls = _text_level_to_class(text_level if isinstance(text_level, int) else None)
                current_heading_path = _update_heading_path(heading_stack, cls, normalize_heading_match_text(text))
                _append_segment(
                    segments,
                    parts,
                    offset_ref,
                    text,
                    heading_path=current_heading_path,
                    page_no=page_no,
                    metadata={
                        "block": "heading",
                        "heading_class": cls,
                        "heading_level": _CLASS_ORDER.get(cls, 3),
                        "heading_path": current_heading_path,
                        "bbox": bbox,
                    },
                )
                heading_count += 1
            elif typ in {"text", "list", "equation", "code"}:
                if typ == "code":
                    text = _preserve_newlines(item.get("code_body") or item.get("text"))
                else:
                    text = _plain_text(item.get("text") or item.get("content"))
                if not text:
                    continue
                meta: dict[str, Any] = {
                    "block": "paragraph",
                    "heading_path": current_heading_path,
                    "bbox": bbox,
                }
                if typ == "equation":
                    meta["equation"] = True
                elif typ == "list":
                    meta["list"] = True
                elif typ == "code":
                    meta["code"] = True
                _append_segment(
                    segments,
                    parts,
                    offset_ref,
                    text,
                    heading_path=current_heading_path,
                    page_no=page_no,
                    metadata=meta,
                )
            elif typ == "table":
                body = item.get("table_body") or item.get("html") or item.get("content")
                if not isinstance(body, str):
                    body = ""
                rows = _table_body_to_rows(body) if body.strip() else []
                if not rows and body.strip():
                    rows = _markdown_table_to_rows(body)
                if not rows:
                    continue
                table_html = body.strip() if body.strip().startswith("<") else ""
                if not table_html and rows:
                    table_html = _grid_to_html_table(rows)
                table_segments = build_table_segments_smart(
                    rows,
                    table_counter,
                    offset_ref,
                    parts,
                    current_heading_path,
                    table_body=body,
                    table_body_html=table_html or None,
                )
                for seg in table_segments:
                    meta = dict(seg.metadata or {})
                    meta["bbox"] = bbox
                    meta["content_list_index"] = cl_index
                    seg.metadata = meta
                    if page_no is not None:
                        seg.page_no = page_no
                segments.extend(table_segments)
                caption = _plain_text(item.get("table_caption"))
                if caption:
                    _append_segment(
                        segments,
                        parts,
                        offset_ref,
                        caption,
                        heading_path=current_heading_path,
                        page_no=page_no,
                        metadata={
                            "block": "table",
                            "table_index": table_counter,
                            "table_role": "caption",
                            "heading_path": current_heading_path,
                        },
                    )
                table_counter += 1
            elif typ == "image":
                caption = _plain_text(item.get("image_caption"))
                ocr = _plain_text(item.get("image_ocr_text") or item.get("description"))
                parts_img = [p for p in (caption, ocr) if p]
                if not parts_img:
                    continue
                _append_segment(
                    segments,
                    parts,
                    offset_ref,
                    " ".join(parts_img),
                    heading_path=current_heading_path,
                    page_no=page_no,
                    metadata={
                        "block": "image",
                        "heading_path": current_heading_path,
                        "bbox": bbox,
                        "img_path": item.get("img_path"),
                    },
                )

        full_text = "\n".join(parts).strip()
        if not full_text and self.markdown:
            full_text = self.markdown.strip()
        return ParsedDocument(
            parser_type="pdf",
            text=full_text,
            char_count=len(full_text),
            segments=segments,
            metadata={
                "parser_backend": "opendataloader",
                "source_file_name": self.source_file_name,
                "heading_count": heading_count,
                "table_count": table_counter,
                "content_list_length": len(content_list),
            },
        )


@dataclass
class OpenDataLoaderGateway:
    enabled: bool
    hybrid: bool
    hybrid_url: str
    timeout: int

    def is_enabled(self) -> bool:
        return bool(self.enabled)

    def parse(
        self,
        file_bytes: bytes,
        file_name: str,
        *,
        use_hybrid: bool | None = None,
        log: Callable[[str], None] | None = None,
    ) -> OpenDataLoaderResult:
        if not self.is_enabled():
            raise OpenDataLoaderUnavailableError("OpenDataLoader 未启用（ODL_ENABLED=false）")
        if not _java_available():
            raise OpenDataLoaderUnavailableError(
                "未找到 Java 运行时。OpenDataLoader 需要 JRE 11+（Docker 镜像请安装 default-jre-headless）。"
            )
        try:
            import opendataloader_pdf
        except ImportError as e:
            raise OpenDataLoaderUnavailableError(
                "未安装 opendataloader-pdf，请 pip install opendataloader-pdf"
            ) from e

        hybrid_on = self.hybrid if use_hybrid is None else use_hybrid
        safe_name = file_name if file_name.lower().endswith(".pdf") else f"{file_name}.pdf"
        n_bytes = len(file_bytes)
        if log:
            log(
                f"OpenDataLoader：解析 PDF「{safe_name}」{n_bytes} 字节"
                f"{'（Hybrid）' if hybrid_on else ''}…"
            )
        t0 = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="zs-rag-odl-") as tmp:
            tmp_path = Path(tmp)
            pdf_path = tmp_path / Path(safe_name).name
            pdf_path.write_bytes(file_bytes)
            out_dir = tmp_path / "out"
            out_dir.mkdir()
            convert_kwargs: dict[str, Any] = {
                "input_path": [str(pdf_path)],
                "output_dir": str(out_dir),
                "format": "json,markdown",
                "quiet": True,
            }
            if hybrid_on:
                convert_kwargs["hybrid"] = "docling-fast"
                convert_kwargs["hybrid_mode"] = "full"
                convert_kwargs["hybrid_url"] = self.hybrid_url
                convert_kwargs["hybrid_timeout"] = str(self.timeout * 1000)
                convert_kwargs["hybrid_fallback"] = True
                if log:
                    try:
                        import httpx

                        probe = self.hybrid_url.rstrip("/") + "/health"
                        resp = httpx.get(probe, timeout=5.0)
                        if resp.status_code >= 400:
                            log(
                                f"警告：Hybrid sidecar 探测 {probe} 返回 HTTP {resp.status_code}；"
                                "若解析结果仍无正文，可能已回退为普通 OpenDataLoader（hybrid_fallback）"
                            )
                        else:
                            log(
                                f"Hybrid sidecar 探测 OK：{probe}（hybrid_mode=full，全部页面走 Docling OCR）"
                            )
                    except Exception as exc:
                        log(
                            f"警告：Hybrid sidecar 不可达（{self.hybrid_url}：{exc}）。"
                            "将尝试 convert，失败时会静默回退为普通 OpenDataLoader；扫描 PDF 请修复 sidecar 或改用 MinerU"
                        )
            try:
                opendataloader_pdf.convert(**convert_kwargs)
            except Exception as e:
                raise OpenDataLoaderUnavailableError(f"OpenDataLoader convert 失败：{e}") from e

            stem = pdf_path.stem
            json_path = out_dir / f"{stem}.json"
            md_path = out_dir / f"{stem}.md"
            if not json_path.is_file():
                candidates = list(out_dir.glob("*.json"))
                json_path = candidates[0] if candidates else json_path
            if not json_path.is_file():
                raise OpenDataLoaderUnavailableError(
                    f"OpenDataLoader 未生成 JSON 输出（目录 {out_dir}）"
                )
            try:
                doc_json = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                raise OpenDataLoaderUnavailableError(f"读取 OpenDataLoader JSON 失败：{e}") from e
            if not isinstance(doc_json, dict):
                raise OpenDataLoaderUnavailableError("OpenDataLoader JSON 根节点不是对象")
            markdown: str | None = None
            if md_path.is_file():
                markdown = md_path.read_text(encoding="utf-8")
            else:
                md_candidates = list(out_dir.glob("*.md"))
                if md_candidates:
                    markdown = md_candidates[0].read_text(encoding="utf-8")

        elapsed = round(time.monotonic() - t0, 2)
        page_heights = _page_heights_from_doc(doc_json)
        elements = _iter_odl_elements(doc_json)
        if log:
            log(
                f"OpenDataLoader：完成，耗时 {elapsed}s，元素 {len(elements)} 个"
                f"，Markdown 约 {len(markdown or '')} 字符"
            )
            if hybrid_on:
                text_elems = sum(
                    1
                    for e in elements
                    if str(e.get("type") or "").lower()
                    in {"paragraph", "heading", "list", "caption", "footnote", "code"}
                    and _element_content(e).strip()
                )
                img_elems = sum(
                    1
                    for e in elements
                    if str(e.get("type") or "").lower() in {"picture", "image", "figure"}
                )
                if img_elems > 0 and text_elems == 0:
                    timeout_hint = ""
                    if elapsed >= self.timeout * 0.9:
                        timeout_hint = (
                            f"耗时 {elapsed}s 已接近 hybrid_timeout={self.timeout}s，"
                            "sidecar 可能仍在 OCR 但已被超时回退；请将 .env ODL_TIMEOUT 调大（扫描 PDF 建议 1800+）。"
                        )
                    else:
                        timeout_hint = (
                            "sidecar 可能转换失败并已 hybrid_fallback 回退；"
                            "请检查 opendataloader-hybrid 日志。"
                        )
                    log(
                        "警告：Hybrid 已启用但结果无 OCR 正文（仅图片占位）。"
                        + timeout_hint
                        + " 扫描 PDF 建议改用 MinerU，或增大 ODL_TIMEOUT 后重试。"
                    )
        return OpenDataLoaderResult(
            doc_json=doc_json,
            markdown=markdown,
            source_file_name=safe_name,
            page_heights=page_heights,
        )


_gateway_lock = threading.Lock()
_gateway_singleton: OpenDataLoaderGateway | None = None


def get_opendataloader_gateway() -> OpenDataLoaderGateway:
    global _gateway_singleton
    if _gateway_singleton is not None:
        return _gateway_singleton
    with _gateway_lock:
        if _gateway_singleton is None:
            s = get_settings()
            _gateway_singleton = OpenDataLoaderGateway(
                enabled=s.odl_enabled,
                hybrid=s.odl_hybrid,
                hybrid_url=s.odl_hybrid_url,
                timeout=s.odl_timeout,
            )
    return _gateway_singleton


def reset_opendataloader_gateway() -> None:
    global _gateway_singleton
    with _gateway_lock:
        _gateway_singleton = None
