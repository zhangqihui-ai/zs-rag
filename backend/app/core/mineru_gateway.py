"""
MinerU HTTP 客户端 + content_list.json → ParsedDocument 映射。

职责范围：
- 按 MINERU_FORMATS 白名单接管 PDF、图片及 Office/表格/文本等后缀
- 具体是否走 MinerU 由知识库 parsers.*.engine 与 document_parser.parse_document 决定
- PDF：失败抛 MineruUnavailableError，由上层 _parse_pdf 降级到 pypdf
- 图片 / 用户显式选择 mineru 的 Office·CSV·文本：失败由上层转为 UnsupportedDocumentError
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import threading
import time
import zipfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.document_parser import (
    ParsedDocument,
    ParsedSegment,
    _CLASS_ORDER,
    _update_heading_path,
    build_table_segments_from_rows,
    build_table_segments_smart,
)
from app.core.heading_match import normalize_heading_match_text

logger = logging.getLogger(__name__)


class MineruUnavailableError(Exception):
    """MinerU 服务不可达 / 超时 / 返回异常。上层据此决定降级或报错。"""


# MinerU /file_parse 支持的 Excel 后缀（旧版 .xls 须用本地 xlrd）
MINERU_EXCEL_SUFFIXES = frozenset({"xlsx", "xlsm"})


def mineru_supports_excel_suffix(suffix: str) -> bool:
    return suffix.lower().lstrip(".") in MINERU_EXCEL_SUFFIXES


# MinerU 写临时目录时对文件名敏感：括号、中文冒号等会导致 pipeline 快速失败（HTTP 409）
_MINERU_UNSAFE_UPLOAD_CHARS = re.compile(
    r'[\\/:*?"<>|()\uFF08\uFF09\uFF1A\uFF1B]|[\x00-\x1f]'
)


def _mineru_safe_upload_filename(file_name: str) -> str:
    """上传 /file_parse 时使用的安全文件名（仅 ASCII，避免 pipeline 写临时目录失败）。"""
    path = Path(file_name)
    suffix = path.suffix.lower() if path.suffix else ".pdf"
    stem = path.stem or "document"
    safe_stem = _MINERU_UNSAFE_UPLOAD_CHARS.sub("_", stem)
    safe_stem = re.sub(r"_+", "_", safe_stem).strip("._ ")
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]", "", safe_stem)
    ascii_stem = re.sub(r"_+", "_", ascii_stem).strip("._-")
    if len(ascii_stem) < 3:
        digest = hashlib.sha256(file_name.encode("utf-8")).hexdigest()[:16]
        ascii_stem = f"doc_{digest}"
    if len(ascii_stem) > 120:
        ascii_stem = ascii_stem[:120]
    return f"{ascii_stem}{suffix}"


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


def _grid_to_markdown_table(rows: list[list[str]]) -> str:
    """二维单元格网格 → GitHub 风格 Markdown 表格（不含 colspan）。"""
    cleaned = [[c.strip() for c in row] for row in rows if any(c.strip() for c in row)]
    if not cleaned:
        return ""
    width = max(len(r) for r in cleaned)
    norm = [r + [""] * (width - len(r)) for r in cleaned]
    lines = ["| " + " | ".join(r) + " |" for r in norm]
    if len(norm) >= 2:
        sep = "| " + " | ".join("---" for _ in range(width)) + " |"
        lines.insert(1, sep)
    return "\n".join(lines)


def _grid_to_html_table(rows: list[list[str]], *, header_rows: int = 1) -> str:
    """二维单元格网格 → HTML table（首行默认 th）。"""
    import html as html_module

    cleaned = [[c.strip() for c in row] for row in rows if any(c.strip() for c in row)]
    if not cleaned:
        return ""
    width = max(len(r) for r in cleaned)
    parts = ['<table>']
    for ri, row in enumerate(cleaned):
        parts.append("<tr>")
        cells = row + [""] * (width - len(row))
        for ci, cell in enumerate(cells):
            tag = "th" if ri < header_rows else "td"
            parts.append(f"<{tag}>{html_module.escape(cell)}</{tag}>")
        parts.append("</tr>")
    parts.append("</table>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# 标题级别 → class 映射（和 document_parser.py 的 _HEADING_CLASSES 语义一致）
# ---------------------------------------------------------------------------

_LEVEL_TO_CLASS = {1: "chapter", 2: "section"}
_MINERU_ATTACHMENT_LABEL_RE = re.compile(
    r"^附件\s*[\d一二三四五六七八九十]*\s*[：:]?\s*$",
    re.IGNORECASE,
)
_MINERU_PAGE_TABLE_CONTEXT_MAX = 120
_MINERU_FOOTER_TEXT_RE = re.compile(
    r"(文件下载链接|https?://|\.pdf\s*$|分享到|【打印】|【关闭】|版权所有|ICP备|政府网站)",
    re.IGNORECASE,
)


def _mineru_text_looks_like_title(text: str) -> bool:
    """MinerU 有时把居中标题标成普通 text（无 text_level），需保留为标题上下文。"""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t or len(t) > 80:
        return False
    if re.search(r"[。！？；;]$", t):
        return False
    if _MINERU_FOOTER_TEXT_RE.search(t):
        return False
    if re.match(r"^附件[：:]", t) and len(t) > 24:
        return False
    return True


def _mineru_should_skip_layout_type(typ: str, text: str) -> bool:
    if typ not in {"header", "footer", "page_number"}:
        return False
    if typ == "header" and text and _MINERU_ATTACHMENT_LABEL_RE.match(text.strip()):
        return False
    return True


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
        page_table_context: dict[int, list[str]] = {}

        def _queue_page_table_context(page: int | None, text: str) -> None:
            if page is None:
                return
            t = text.strip()
            if not t:
                return
            bucket = page_table_context.setdefault(page, [])
            if not bucket or bucket[-1] != t:
                bucket.append(t)

        def _take_page_table_context(page: int | None) -> str:
            if page is None:
                return ""
            lines = page_table_context.pop(page, [])
            if not lines:
                return ""
            return "\n\n".join(lines)

        for cl_index, item in enumerate(self.content_list):
            if not isinstance(item, dict):
                continue
            typ = str(item.get("type") or "").lower()
            page_idx = item.get("page_idx")
            page_no = (page_idx + 1) if isinstance(page_idx, int) else None
            bbox = item.get("bbox") if isinstance(item.get("bbox"), list) else None
            text_level = item.get("text_level")
            raw_text = _plain_text(item.get("text") or item.get("content"))

            if _mineru_should_skip_layout_type(typ, raw_text):
                continue

            treat_header_attachment_as_heading = typ == "header" and bool(
                raw_text and _MINERU_ATTACHMENT_LABEL_RE.match(raw_text.strip())
            )

            # 3.x 版本的标题在 type=text + text_level；旧版可能是 type=title
            is_heading = (
                typ == "title"
                or (typ == "text" and text_level)
                or treat_header_attachment_as_heading
                or (typ == "text" and _mineru_text_looks_like_title(raw_text))
            )
            if is_heading:
                text = raw_text
                if not text:
                    continue
                cls = _text_level_to_class(text_level)
                current_heading_path = _update_heading_path(heading_stack, cls, normalize_heading_match_text(text))
                _queue_page_table_context(page_no, text)
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
                if len(text) <= _MINERU_PAGE_TABLE_CONTEXT_MAX:
                    _queue_page_table_context(page_no, text)
            elif typ == "table":
                body = item.get("table_body") or item.get("html") or item.get("content")
                if not isinstance(body, str):
                    continue
                rows = _table_body_to_rows(body)
                table_html = body.strip() if body.strip().startswith("<") else ""
                if not table_html and rows:
                    table_html = _grid_to_html_table(rows)
                caption = _plain_text(item.get("table_caption"))
                if caption:
                    _queue_page_table_context(page_no, caption)
                context_prefix = _take_page_table_context(page_no)
                table_segments = build_table_segments_smart(
                    rows,
                    table_counter,
                    offset_ref,
                    parts,
                    current_heading_path,
                    table_body=body,
                    table_body_html=table_html or None,
                    page_no=page_no,
                    context_prefix=context_prefix or None,
                )
                for seg in table_segments:
                    meta = dict(seg.metadata or {})
                    meta["bbox"] = bbox
                    meta["content_list_index"] = cl_index
                    seg.metadata = meta
                    if page_no is not None:
                        seg.page_no = page_no
                segments.extend(table_segments)
                if caption and not any(caption in (s.text or "") for s in table_segments):
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
                caption = _image_caption_text(item)
                ocr = _image_ocr_text(item)
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
                        "content_list_index": cl_index,
                        **({"image_caption": caption} if caption else {}),
                        **({"image_ocr_text": ocr} if ocr else {}),
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
    if isinstance(value, list):
        if not value:
            return ""
        if all(isinstance(x, str) for x in value):
            joined = " ".join(x.strip() for x in value if x and str(x).strip())
            return re.sub(r"\s+", " ", joined).strip()
        return ""
    if isinstance(value, dict):
        return ""
    s = str(value).strip()
    if s in {"[]", "{}"}:
        return ""
    return re.sub(r"\s+", " ", s)


def _image_caption_text(item: dict[str, Any]) -> str:
    return _plain_text(item.get("image_caption"))


def _image_ocr_text(item: dict[str, Any]) -> str:
    for key in ("image_ocr_text", "ocr_text", "caption", "description", "text"):
        text = _plain_text(item.get(key))
        if text:
            return text
    return ""


def _image_needs_ocr(item: dict[str, Any]) -> bool:
    if str(item.get("type") or "").lower() != "image":
        return False
    return not _image_caption_text(item) and not _image_ocr_text(item)


def _strip_md_images(md: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", md)
    return re.sub(r"\s+", " ", text).strip()


def _extract_md_from_payload(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("md_content", "markdown", "md"):
            md = payload.get(key)
            if isinstance(md, str) and md.strip():
                return md
        for v in payload.values():
            got = _extract_md_from_payload(v)
            if got:
                return got
    elif isinstance(payload, list):
        for v in payload:
            got = _extract_md_from_payload(v)
            if got:
                return got
    return None


def _parse_zip_response(zip_bytes: bytes) -> tuple[list[dict[str, Any]], str | None, dict[str, bytes]]:
    """从 MinerU ZIP 响应提取 content_list、markdown 与内嵌图片 bytes（按文件名索引）。"""
    content_list: list[dict[str, Any]] = []
    markdown: str | None = None
    images: dict[str, bytes] = {}

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        content_list_name = ""
        for name in zf.namelist():
            lower = name.lower()
            if lower.endswith("_content_list.json") and "content_list_v2" not in lower:
                if not content_list_name or len(name) < len(content_list_name):
                    content_list_name = name
            elif lower.endswith(".md") and "/images/" not in lower and markdown is None:
                markdown = zf.read(name).decode("utf-8", errors="replace")
            elif "/images/" in lower or lower.startswith("images/"):
                blob = zf.read(name)
                images[Path(name).name] = blob
                tail = name.split("images/", 1)[-1]
                if tail:
                    images[tail] = blob
        if content_list_name:
            raw = json.loads(zf.read(content_list_name))
            if isinstance(raw, list):
                content_list = raw

    return content_list, markdown, images


_OFFICE_EMBEDDED_IMAGE_SUFFIXES = frozenset({"docx", "pptx", "ppt"})
_MAX_IMAGE_OCR_WORKERS = 4


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
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    "csv": "text/csv",
    "md": "text/markdown",
    "txt": "text/plain",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "ppt": "application/vnd.ms-powerpoint",
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
        norm = suffix.lower().lstrip(".")
        if norm == "xls":
            return False
        return norm in self.format_whitelist

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
        use_zip = suffix in _OFFICE_EMBEDDED_IMAGE_SUFFIXES
        upload_name = _mineru_safe_upload_filename(file_name)
        files = {"files": (upload_name, file_bytes, mime)}
        data = {
            "backend": self.backend,
            "lang_list": [self.lang],
            "parse_method": "ocr" if use_zip else "auto",
            "return_md": "true",
            "return_content_list": "true",
            "return_middle_json": "false",
            "return_layout_pdf": "false",
            "return_images": "true" if use_zip else "false",
            "response_format_zip": "true" if use_zip else "false",
        }
        n_bytes = len(file_bytes)
        mb = n_bytes / (1024 * 1024)
        if log:
            name_note = f"上传名 {upload_name}" if upload_name != file_name else f"文件「{file_name}」"
            log(
                f"MinerU：POST {url}，{name_note}，{n_bytes} 字节（约 {mb:.2f} MB），"
                f"backend={self.backend} lang={self.lang}，超时上限 {self.timeout}s。"
            )
            if use_zip:
                log("MinerU：Office 文档将使用 ZIP 响应并提取内嵌图片，供二次 OCR。")
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
            detail = resp.text[:800]
            try:
                err_body = resp.json()
                if isinstance(err_body, dict):
                    for key in ("error", "message", "detail", "stderr", "traceback"):
                        val = err_body.get(key)
                        if val:
                            detail = str(val)[:800]
                            break
            except ValueError:
                pass
            raise MineruUnavailableError(
                f"MinerU HTTP {resp.status_code}：{detail}"
            )

        content_type = (resp.headers.get("content-type") or "").lower()
        is_zip = use_zip or content_type.startswith("application/zip") or resp.content[:2] == b"PK"
        payload: dict[str, Any] | None = None

        if is_zip:
            if log:
                log("MinerU：正在解析 ZIP 响应（content_list + 内嵌图片）…")
            content_list, md, images = _parse_zip_response(resp.content)
            if not content_list:
                raise MineruUnavailableError("MinerU ZIP 响应中未找到 content_list")
            self._enrich_content_list_images(content_list, images, log=log)
        else:
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
            img_with_text = sum(
                1 for item in content_list if isinstance(item, dict) and str(item.get("type")).lower() == "image" and _image_ocr_text(item)
            )
            log(
                f"MinerU：已得到 content_list 共 {len(content_list)} 条；markdown 约 {md_len} 字符；"
                f"含 OCR 文本的内嵌图 {img_with_text} 张。"
            )
        return MineruResult(
            content_list=content_list,
            markdown=md,
            source_file_name=file_name,
            raw_payload=payload,
            http_status=resp.status_code,
        )

    def _enrich_content_list_images(
        self,
        content_list: list[dict[str, Any]],
        images: dict[str, bytes],
        *,
        log: Callable[[str], None] | None = None,
    ) -> int:
        """Word/PPT 内嵌图 MinerU 常不自带 OCR；对缺文本的图片块逐张二次 OCR。"""
        todo: list[tuple[int, dict[str, Any]]] = [
            (idx, item)
            for idx, item in enumerate(content_list)
            if isinstance(item, dict) and _image_needs_ocr(item)
        ]
        if not todo:
            return 0
        if not images:
            if log:
                log("MinerU：content_list 含图片块但未从 ZIP 拿到图片文件，跳过内嵌图 OCR。")
            return 0

        if log:
            log(f"MinerU：内嵌图 {len(todo)} 张缺少 OCR 文本，开始二次 OCR（并发 {_MAX_IMAGE_OCR_WORKERS}）…")

        enriched = 0

        def _run_one(entry: tuple[int, dict[str, Any]]) -> tuple[int, str]:
            idx, item = entry
            img_path = str(item.get("img_path") or "")
            key = Path(img_path).name
            blob = images.get(key) or images.get(img_path.lstrip("/"))
            if not blob:
                return idx, ""
            ocr = self._ocr_image_bytes(blob, key)
            return idx, ocr

        with ThreadPoolExecutor(max_workers=_MAX_IMAGE_OCR_WORKERS) as pool:
            futures = [pool.submit(_run_one, entry) for entry in todo]
            for fut in as_completed(futures):
                idx, ocr = fut.result()
                if not ocr:
                    continue
                item = content_list[idx]
                item["image_ocr_text"] = ocr
                enriched += 1

        if log:
            log(f"MinerU：内嵌图 OCR 完成，{enriched}/{len(todo)} 张获得可检索文本。")
        return enriched

    def _ocr_image_bytes(self, image_bytes: bytes, file_name: str) -> str:
        """对单张图片调用 MinerU OCR，返回纯文本（去掉 Markdown 图片占位）。"""
        url = self.base_url.rstrip("/") + "/file_parse"
        suffix = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "png"
        mime = _MIME_MAP.get(suffix, "application/octet-stream")
        data = {
            "backend": self.backend,
            "lang_list": [self.lang],
            "parse_method": "ocr",
            "return_md": "true",
            "return_content_list": "false",
            "return_middle_json": "false",
            "response_format_zip": "false",
        }
        upload_name = _mineru_safe_upload_filename(file_name)
        files = {"files": (upload_name, image_bytes, mime)}
        try:
            with httpx.Client(timeout=min(self.timeout, 120)) as client:
                resp = client.post(url, files=files, data=data)
        except httpx.HTTPError:
            return ""
        if resp.status_code >= 400:
            return ""
        try:
            payload = resp.json()
        except ValueError:
            return ""
        md = _extract_md_from_payload(payload)
        if md:
            return _strip_md_images(md)
        content_list, _ = _extract_content_list_and_md(payload)
        texts: list[str] = []
        for item in content_list:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "").lower() in {"text", "title"}:
                t = _plain_text(item.get("text") or item.get("content"))
                if t:
                    texts.append(t)
        return _strip_md_images(" ".join(texts))


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
