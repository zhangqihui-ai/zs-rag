"""
MinerU HTTP 客户端 + content_list.json → ParsedDocument 映射。

职责范围（结合 plan 的"〇、格式分工"）：
- 仅处理 PDF 和图片（PNG/JPG/JPEG/BMP/TIF/TIFF/WEBP）
- DOCX/XLSX/PPTX 等不在本模块处理，由 document_parser.py 里的本地解析器负责
- PDF 场景：失败抛 MineruUnavailableError，由上层 _parse_pdf 降级到 pypdf
- 图片场景：失败抛 MineruUnavailableError，由上层转成 UnsupportedDocumentError（现阶段无降级路径）
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.document_parser import (
    ParsedDocument,
    ParsedSegment,
    _CLASS_ORDER,
    _update_heading_path,
    build_table_segments_from_rows,
)

logger = logging.getLogger(__name__)


class MineruUnavailableError(Exception):
    """MinerU 服务不可达 / 超时 / 返回异常。上层据此决定降级或报错。"""


# ---------------------------------------------------------------------------
# 表格解析：兼容 MinerU 返回的 HTML <table> 和 markdown pipe 两种格式
# ---------------------------------------------------------------------------


class _TableHTMLParser(HTMLParser):
    """简易 HTML 表格 → list[list[str]] 解析器。"""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell_chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_chunks = []
        elif tag == "br" and self._cell_chunks is not None:
            self._cell_chunks.append(" ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"td", "th"} and self._row is not None and self._cell_chunks is not None:
            text = re.sub(r"\s+", " ", "".join(self._cell_chunks)).strip()
            self._row.append(text)
            self._cell_chunks = None
        elif tag == "tr" and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell_chunks is not None:
            self._cell_chunks.append(data)


def _html_table_to_rows(html: str) -> list[list[str]]:
    parser = _TableHTMLParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as e:  # noqa: BLE001
        logger.warning("MinerU HTML 表格解析失败：%s", e)
        return []
    return parser.rows


def _markdown_table_to_rows(md: str) -> list[list[str]]:
    """
    解析形如:
        | 列1 | 列2 |
        | --- | --- |
        | a  | b  |
    的 markdown 表格。跳过分隔行（含 `---` 或 `:---`）。
    """
    rows: list[list[str]] = []
    for raw in md.splitlines():
        line = raw.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        inner = line[1:-1]
        cells = [c.strip() for c in inner.split("|")]
        if cells and all(re.fullmatch(r":?-+:?", c) or not c for c in cells):
            continue
        rows.append(cells)
    return rows


def _table_body_to_rows(body: str) -> list[list[str]]:
    if not body:
        return []
    stripped = body.strip()
    if stripped.startswith("<"):
        return _html_table_to_rows(stripped)
    return _markdown_table_to_rows(stripped)


# ---------------------------------------------------------------------------
# 标题级别 → class 映射（和 document_parser.py 的 _HEADING_CLASSES 语义一致）
# ---------------------------------------------------------------------------

_LEVEL_TO_CLASS = {1: "chapter", 2: "section"}


def _text_level_to_class(text_level: int | None) -> str:
    """
    MinerU 的 text_level 通常是 1/2/3...
    我们映射到和 docx 解析一致的 chapter/section/item 三级分类，方便 _update_heading_path 统一管理栈。
    """
    if text_level is None:
        return "section"
    if text_level in _LEVEL_TO_CLASS:
        return _LEVEL_TO_CLASS[text_level]
    return "item"


# ---------------------------------------------------------------------------
# 解析 /file_parse 响应：兼容多种 payload shape
# ---------------------------------------------------------------------------


def _coerce_content_list(value: Any) -> list[dict[str, Any]] | None:
    """
    content_list 在不同 MinerU 版本下可能是 list，也可能是 JSON 字符串（task 风格响应里会被序列化为 str）。
    这里尽量兜住两种形态，失败返回 None。
    """
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().startswith("["):
        import json as _json

        try:
            parsed = _json.loads(value)
        except ValueError:
            return None
        if isinstance(parsed, list):
            return parsed
    return None


def _extract_content_list_and_md(payload: Any) -> tuple[list[dict[str, Any]], str | None]:
    """
    MinerU 不同版本/不同参数下 payload 形态略有不同，尽量鲁棒地提取 content_list + markdown：
    - {"content_list": [...], "md_content": "..."}
    - {"<filename>": {"content_list": [...], "md_content": "..."}}
    - {"data": { ... above ... }}
    - {"results": [{ ... }]}
    - {"results": {"<filename>": { ... }}}               # 3.x task 风格
    - content_list 可能是 JSON 字符串而非直接 list（3.x task 风格）
    """
    if isinstance(payload, dict):
        cl = _coerce_content_list(payload.get("content_list"))
        if cl is not None:
            md = payload.get("md_content") or payload.get("markdown") or payload.get("md")
            return cl, md if isinstance(md, str) else None
        data = payload.get("data")
        if isinstance(data, (dict, list)):
            got = _extract_content_list_and_md(data)
            if got[0]:
                return got
        results = payload.get("results")
        if isinstance(results, (dict, list)):
            got = _extract_content_list_and_md(results)
            if got[0]:
                return got
        for v in payload.values():
            if isinstance(v, (dict, list)):
                got = _extract_content_list_and_md(v)
                if got[0]:
                    return got
    elif isinstance(payload, list):
        for item in payload:
            got = _extract_content_list_and_md(item)
            if got[0]:
                return got
    return [], None


# ---------------------------------------------------------------------------
# content_list → ParsedDocument
# ---------------------------------------------------------------------------


@dataclass
class MineruResult:
    """MinerU /file_parse 返回的结构化结果。"""

    content_list: list[dict[str, Any]]
    markdown: str | None = None
    source_file_name: str = "doc"
    raw_payload: dict[str, Any] | None = None
    http_status: int | None = None

    def to_parsed_document(self) -> ParsedDocument:
        segments: list[ParsedSegment] = []
        parts: list[str] = []
        offset_ref = [0]
        heading_stack: list[tuple[str, str]] = []
        current_heading_path: str | None = None
        table_counter = 0
        heading_count = 0

        for item in self.content_list:
            if not isinstance(item, dict):
                continue
            typ = str(item.get("type") or "").lower()
            page_idx = item.get("page_idx")
            page_no = (page_idx + 1) if isinstance(page_idx, int) else None
            bbox = item.get("bbox") if isinstance(item.get("bbox"), list) else None
            text_level = item.get("text_level")

            # 页眉/页码：不是正文，直接丢弃
            if typ in {"header", "footer", "page_number"}:
                continue

            # 3.x 版本的标题在 type=text + text_level；旧版可能是 type=title
            is_heading = typ == "title" or (typ == "text" and text_level)
            if is_heading:
                text = _plain_text(item.get("text") or item.get("content"))
                if not text:
                    continue
                cls = _text_level_to_class(text_level)
                current_heading_path = _update_heading_path(heading_stack, cls, text)
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
                    raw = item.get("code_body") or item.get("text") or item.get("content")
                    text = _preserve_newlines(raw)
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
                    sub = item.get("sub_type") or item.get("language") or item.get("lang")
                    if sub:
                        meta["code_sub_type"] = sub
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
                    continue
                rows = _table_body_to_rows(body)
                table_segments = build_table_segments_from_rows(
                    rows,
                    table_counter,
                    offset_ref,
                    parts,
                    current_heading_path,
                )
                for seg in table_segments:
                    meta = dict(seg.metadata or {})
                    meta["bbox"] = bbox
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
                ocr = _plain_text(item.get("image_ocr_text") or item.get("caption"))
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
        return ParsedDocument(
            parser_type="mineru",
            text=full_text,
            char_count=len(full_text),
            segments=segments,
            metadata={
                "parser_backend": "mineru",
                "source_file_name": self.source_file_name,
                "heading_count": heading_count,
                "table_count": table_counter,
                "content_list_length": len(self.content_list),
            },
        )


def _plain_text(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return re.sub(r"\s+", " ", s)


def _preserve_newlines(value: Any) -> str:
    """给代码块用：归一行内空白但保留换行，避免 ``for ... {`` 整块被压成一行。"""
    if value is None:
        return ""
    s = str(value).replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in s.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _append_segment(
    segments: list[ParsedSegment],
    parts: list[str],
    offset_ref: list[int],
    text: str,
    *,
    heading_path: str | None,
    page_no: int | None,
    metadata: dict[str, Any],
) -> None:
    start = offset_ref[0]
    end = start + len(text)
    segments.append(
        ParsedSegment(
            text=text,
            start_offset=start,
            end_offset=end,
            page_no=page_no,
            heading_path=heading_path,
            metadata=metadata,
        )
    )
    parts.append(text)
    offset_ref[0] = end + 1


# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------


_MIME_MAP = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "webp": "image/webp",
}


@dataclass
class MineruGateway:
    enabled: bool
    base_url: str
    backend: str
    lang: str
    timeout: int
    format_whitelist: set[str] = field(default_factory=set)

    def is_enabled(self) -> bool:
        return bool(self.enabled and self.base_url)

    def should_handle(self, suffix: str) -> bool:
        if not self.is_enabled():
            return False
        return suffix.lower().lstrip(".") in self.format_whitelist

    def parse(
        self,
        file_bytes: bytes,
        file_name: str,
        *,
        log: Callable[[str], None] | None = None,
    ) -> MineruResult:
        """同步调 /file_parse，超时/HTTP 错误/payload 异常统一抛 MineruUnavailableError。"""
        if not self.is_enabled():
            raise MineruUnavailableError("MinerU 未启用")
        url = self.base_url.rstrip("/") + "/file_parse"
        suffix = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "pdf"
        mime = _MIME_MAP.get(suffix, "application/octet-stream")
        files = {"files": (file_name, file_bytes, mime)}
        data = {
            "backend": self.backend,
            "lang": self.lang,
            "return_md": "true",
            "return_content_list": "true",
            "return_middle_json": "false",
            "return_layout_pdf": "false",
            "response_format_zip": "false",
        }
        n_bytes = len(file_bytes)
        mb = n_bytes / (1024 * 1024)
        if log:
            log(
                f"MinerU：POST {url}，文件「{file_name}」{n_bytes} 字节（约 {mb:.2f} MB），"
                f"backend={self.backend} lang={self.lang}，超时上限 {self.timeout}s。"
            )
            log("MinerU：正在上传并等待服务端解析（版面分析/OCR，大文件可能需数分钟）…")
        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, files=files, data=data)
        except httpx.TimeoutException as e:
            raise MineruUnavailableError(f"MinerU 请求超时（>{self.timeout}s）：{e}") from e
        except httpx.HTTPError as e:
            raise MineruUnavailableError(f"MinerU 网络错误：{e}") from e
        elapsed = round(time.monotonic() - t0, 1)
        body_len = len(resp.content or b"")
        if log:
            log(f"MinerU：HTTP 响应 {resp.status_code}，耗时 {elapsed}s，响应体约 {body_len} 字节。")
        if resp.status_code >= 400:
            raise MineruUnavailableError(
                f"MinerU HTTP {resp.status_code}：{resp.text[:200]}"
            )
        if log:
            log("MinerU：正在解析响应 JSON…")
        try:
            payload = resp.json()
        except ValueError as e:
            raise MineruUnavailableError(f"MinerU 返回非 JSON：{resp.text[:200]}") from e
        if log and isinstance(payload, dict):
            keys = ", ".join(sorted(payload.keys())[:12])
            more = "…" if len(payload) > 12 else ""
            log(f"MinerU：JSON 顶层字段（节选）：{keys}{more}")
        if log:
            log("MinerU：正在提取 content_list / markdown…")
        content_list, md = _extract_content_list_and_md(payload)
        if not content_list:
            raise MineruUnavailableError(
                "MinerU 返回 payload 中未找到 content_list（可能是 API 版本不匹配或解析失败）"
            )
        md_len = len(md) if md else 0
        if log:
            log(f"MinerU：已得到 content_list 共 {len(content_list)} 条；markdown 约 {md_len} 字符。")
        return MineruResult(
            content_list=content_list,
            markdown=md,
            source_file_name=file_name,
            raw_payload=payload if isinstance(payload, dict) else None,
            http_status=resp.status_code,
        )


_gateway_lock = threading.Lock()
_gateway_singleton: MineruGateway | None = None


def get_mineru_gateway() -> MineruGateway:
    """进程内单例。配置变化需重启进程生效（与 settings 一致）。"""
    global _gateway_singleton
    if _gateway_singleton is not None:
        return _gateway_singleton
    with _gateway_lock:
        if _gateway_singleton is None:
            s = get_settings()
            _gateway_singleton = MineruGateway(
                enabled=s.mineru_enabled,
                base_url=s.mineru_base_url,
                backend=s.mineru_backend,
                lang=s.mineru_lang,
                timeout=s.mineru_timeout,
                format_whitelist=s.mineru_format_set,
            )
    return _gateway_singleton


def reset_mineru_gateway() -> None:
    """测试/热更新用。"""
    global _gateway_singleton
    with _gateway_lock:
        _gateway_singleton = None
