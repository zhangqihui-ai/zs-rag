from __future__ import annotations

import csv
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from io import BytesIO, StringIO
from typing import Any

try:
    from docx import Document as DocxDocument
    from docx.table import Table as DocxTable, _Cell as DocxCell  # type: ignore[attr-defined]
    from docx.text.paragraph import Paragraph as DocxParagraph
    from docx.oxml.ns import qn as docx_qn  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover
    DocxDocument = None  # type: ignore
    DocxTable = None  # type: ignore
    DocxCell = None  # type: ignore
    DocxParagraph = None  # type: ignore
    docx_qn = None  # type: ignore

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover
    load_workbook = None  # type: ignore

try:
    import xlrd
except ImportError:  # pragma: no cover
    xlrd = None  # type: ignore

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore


class UnsupportedDocumentError(Exception):
    """无法解析或格式暂不支持（需在业务层转统一错误）。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class ParsedSegment:
    text: str
    start_offset: int
    end_offset: int
    page_no: int | None = None
    heading_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    parser_type: str
    text: str
    char_count: int
    segments: list[ParsedSegment]
    metadata: dict[str, Any] = field(default_factory=dict)


def _decode_text_content(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="ignore")


def _split_markdown_sections(text: str) -> list[tuple[str, str | None]]:
    lines = text.splitlines()
    sections: list[tuple[str, str | None]] = []
    heading_stack: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        content = "\n".join(buffer).strip()
        if content:
            sections.append((content, " / ".join(heading_stack) or None))
        buffer.clear()

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match:
            flush()
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            heading_stack[:] = heading_stack[: level - 1]
            heading_stack.append(heading_text)
            buffer.append(line)
        else:
            buffer.append(line)

    flush()
    if not sections and text.strip():
        sections.append((text.strip(), None))
    return sections


def _build_segments_from_sections(sections: list[tuple[str, str | None]]) -> list[ParsedSegment]:
    segments: list[ParsedSegment] = []
    offset = 0
    for section_text, heading_path in sections:
        text = section_text.strip()
        if not text:
            continue
        start_offset = offset
        end_offset = start_offset + len(text)
        segments.append(
            ParsedSegment(
                text=text,
                start_offset=start_offset,
                end_offset=end_offset,
                heading_path=heading_path,
                metadata={"heading_path": heading_path},
            )
        )
        offset = end_offset + 2
    return segments


def _decode_pdf_escape_sequences(value: str) -> str:
    def _octal_replace(match: re.Match[str]) -> str:
        return chr(int(match.group(1), 8))

    value = re.sub(r"\\([0-7]{1,3})", _octal_replace, value)
    value = (
        value.replace(r"\\n", "\n")
        .replace(r"\\r", "\r")
        .replace(r"\\t", "\t")
        .replace(r"\\b", "\b")
        .replace(r"\\f", "\f")
        .replace(r"\\(", "(")
        .replace(r"\\)", ")")
        .replace(r"\\\\", "\\")
    )
    return value


def _extract_pdf_text_fallback(file_bytes: bytes) -> str:
    stream_pattern = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
    literal_pattern = re.compile(r"\((.*?)(?<!\\)\)")
    texts: list[str] = []

    for stream_match in stream_pattern.finditer(file_bytes):
        stream_bytes = stream_match.group(1)
        candidates = [stream_bytes]
        try:
            import zlib

            candidates.append(zlib.decompress(stream_bytes))
        except Exception:
            pass

        for candidate in candidates:
            decoded = candidate.decode("latin-1", errors="ignore")
            if "Tj" not in decoded and "TJ" not in decoded:
                continue
            for raw in literal_pattern.findall(decoded):
                text = _decode_pdf_escape_sequences(raw).strip()
                if text:
                    texts.append(text)

    merged = "\n".join(texts)
    merged = re.sub(r"\s+", " ", merged).strip()
    return merged


def _parse_pdf(
    file_bytes: bytes,
    *,
    file_name: str | None = None,
    log: Callable[[str], None] | None = None,
) -> ParsedDocument:
    # 优先交给 MinerU（若启用且可达）；失败时降级到本地 pypdf 兜底
    try:
        from app.core.mineru_gateway import MineruUnavailableError, get_mineru_gateway
    except Exception:  # pragma: no cover
        MineruUnavailableError = Exception  # type: ignore[assignment]
        get_mineru_gateway = None  # type: ignore[assignment]
    if get_mineru_gateway is not None:
        gw = get_mineru_gateway()
        if gw.should_handle("pdf"):
            try:
                if log:
                    log(f"使用 MinerU 解析 PDF（backend={gw.backend}, lang={gw.lang}）…")
                result = gw.parse(file_bytes, file_name or "doc.pdf")
                doc = result.to_parsed_document()
                if log:
                    log(
                        f"MinerU：字符数 {doc.char_count}，分段 {len(doc.segments)}，"
                        f"标题 {doc.metadata.get('heading_count')}，表格 {doc.metadata.get('table_count')}"
                    )
                return doc
            except MineruUnavailableError as e:
                if log:
                    log(f"MinerU 不可用，降级到 pypdf：{e}")

    if log:
        log("使用 pypdf 解析 PDF…")
    if PdfReader is not None:
        try:
            reader = PdfReader(BytesIO(file_bytes))
            segments: list[ParsedSegment] = []
            texts: list[str] = []
            offset = 0

            for index, page in enumerate(reader.pages, start=1):
                page_text = (page.extract_text() or "").strip()
                if not page_text:
                    continue
                texts.append(page_text)
                start_offset = offset
                end_offset = start_offset + len(page_text)
                segments.append(
                    ParsedSegment(
                        text=page_text,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        page_no=index,
                        metadata={"page_no": index},
                    )
                )
                offset = end_offset + 2

            full_text = "\n\n".join(texts).strip()
            if full_text:
                return ParsedDocument(
                    parser_type="pdf",
                    text=full_text,
                    char_count=len(full_text),
                    segments=segments,
                    metadata={
                        "parser_backend": "pypdf",
                        "page_count": len(reader.pages),
                        "parsed_page_count": len(segments),
                    },
                )
        except Exception:
            pass

    fallback_text = _extract_pdf_text_fallback(file_bytes)
    if not fallback_text:
        return ParsedDocument(
            parser_type="pdf",
            text="",
            char_count=0,
            segments=[],
            metadata={"parser_backend": "pypdf_fallback", "fallback": True},
        )

    segment = ParsedSegment(
        text=fallback_text,
        start_offset=0,
        end_offset=len(fallback_text),
        metadata={"fallback": True},
    )
    return ParsedDocument(
        parser_type="pdf",
        text=fallback_text,
        char_count=len(fallback_text),
        segments=[segment],
        metadata={"parser_backend": "pypdf_fallback", "fallback": True},
    )


# 章节标题识别（启发式）：优先依赖 Word Heading 样式；无样式回退到中文/数字特征。
# 用"等级类（class）"而非绝对级别，避免章/节/条混杂时栈层级错乱。
_CN_NUM = r"[一二三四五六七八九十百千]+"
_HEADING_CLASSES: list[tuple[str, "re.Pattern[str]"]] = [
    # chapter（章）：第X章、一、背景介绍、第1章
    ("chapter", re.compile(rf"^第\s*{_CN_NUM}\s*[章节篇部].{{0,60}}$")),
    ("chapter", re.compile(rf"^{_CN_NUM}\s*[、.．].{{0,60}}$")),
    ("chapter", re.compile(r"^第\s*\d+\s*[章节篇部条款].{0,60}$")),
    # section（节）：（一）xxx、1.1 xxx、1.2.3 xxx
    ("section", re.compile(rf"^[(（]\s*{_CN_NUM}\s*[)）].{{0,60}}$")),
    ("section", re.compile(r"^\d+(?:\.\d+){1,3}\s+.{0,60}$")),
    # item（条/款）：1、xxx、2. xxx、3) xxx —— 严格限制长度避免把正文里的枚举列表误判
    ("item", re.compile(r"^\d+\s*[、.．)）]\s*.{1,22}$")),
]

_CLASS_ORDER = {"chapter": 1, "section": 2, "item": 3}


def _style_heading_class(style_name: str | None) -> str | None:
    if not style_name:
        return None
    m = re.match(r"^(?:Heading|标题)\s*(\d+)$", style_name.strip(), re.IGNORECASE)
    if not m:
        return None
    level = int(m.group(1))
    if level <= 1:
        return "chapter"
    if level == 2:
        return "section"
    if level >= 3:
        return "item"
    return None


def _detect_heading_class(text: str, style_name: str | None) -> str | None:
    cls = _style_heading_class(style_name)
    if cls is not None:
        return cls
    t = text.strip()
    if not t or len(t) > 60:
        return None
    t_norm = t.replace("\u3000", " ")
    for class_tag, regex in _HEADING_CLASSES:
        if regex.match(t_norm):
            return class_tag
    return None


def _update_heading_path(stack: list[tuple[str, str]], heading_class: str, text: str) -> str:
    """
    按 class 等级维护标题栈：
    - 同 class → 同级替换；
    - 更低 class → 保留；
    - 更高或同级 → 截断。
    """
    cur_order = _CLASS_ORDER.get(heading_class, 3)
    new_stack: list[tuple[str, str]] = []
    for cls, t in stack:
        if _CLASS_ORDER.get(cls, 3) < cur_order:
            new_stack.append((cls, t))
        else:
            break
    new_stack.append((heading_class, text.strip()))
    stack[:] = new_stack
    return " / ".join(t for _, t in new_stack)


def _docx_table_cell_text(cell: "DocxCell") -> str:
    """把单元格内所有段落拼成一行文本（去换行，保留空格）。"""
    try:
        paragraphs = cell.paragraphs  # type: ignore[attr-defined]
    except Exception:
        return (cell.text or "").strip().replace("\n", " ")
    pieces = [p.text.strip() for p in paragraphs if (p.text or "").strip()]
    return " ".join(pieces) if pieces else (cell.text or "").strip().replace("\n", " ")


def _is_plausible_header_row(cells: list[str]) -> bool:
    """启发式：若首行均不为空、且没有显著长于其他行的值，视为表头。"""
    if not cells or any(not c for c in cells):
        return False
    if any(len(c) > 40 for c in cells):
        return False
    return True


def build_table_segments_from_rows(
    rows: list[list[str]],
    ti: int,
    offset_ref: list[int],
    parts: list[str],
    heading_path: str | None,
) -> list[ParsedSegment]:
    """
    通用"行 → 表格 ParsedSegment 列表"转换器：
    - 第 1 个 segment：表格概览（表头 + 行数），便于"这个表格是关于什么"类召回
    - 每个数据行：一个 segment，文本为 "列1：值1；列2：值2"（若有表头）或 "值1 | 值2..."（无表头）

    offset_ref 是 [current_offset] 的可变引用，用于累加偏移，保持与全文 offset 一致。
    docx、MinerU PDF 表格等不同来源都应归一到 list[list[str]] 后调用本函数。
    """
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return []

    header: list[str] | None = None
    if len(rows) >= 2 and _is_plausible_header_row(rows[0]):
        header = rows[0]
        data_rows = rows[1:]
    else:
        data_rows = rows

    segments: list[ParsedSegment] = []

    overview_parts: list[str] = [f"表格 {ti + 1}"]
    if header:
        overview_parts.append("列：" + " | ".join(header))
    overview_parts.append(f"共 {len(data_rows)} 行")
    overview = "；".join(overview_parts)
    start = offset_ref[0]
    end = start + len(overview)
    segments.append(
        ParsedSegment(
            text=overview,
            start_offset=start,
            end_offset=end,
            heading_path=heading_path,
            metadata={
                "block": "table",
                "table_index": ti,
                "table_role": "overview",
                "table_header": header,
                "table_row_count": len(data_rows),
                "heading_path": heading_path,
            },
        )
    )
    parts.append(overview)
    offset_ref[0] = end + 1

    for ri, cells in enumerate(data_rows):
        if header and len(cells) == len(header):
            line = "；".join(f"{h}：{v}" for h, v in zip(header, cells) if v)
        else:
            line = " | ".join(c for c in cells if c)
        line = line.strip()
        if not line:
            continue
        start = offset_ref[0]
        end = start + len(line)
        segments.append(
            ParsedSegment(
                text=line,
                start_offset=start,
                end_offset=end,
                heading_path=heading_path,
                metadata={
                    "block": "table",
                    "table_index": ti,
                    "table_role": "row",
                    "table_row_index": ri,
                    "table_header": header,
                    "heading_path": heading_path,
                },
            )
        )
        parts.append(line)
        offset_ref[0] = end + 1

    return segments


def _docx_table_to_segments(
    table: "DocxTable",
    ti: int,
    offset_ref: list[int],
    parts: list[str],
    heading_path: str | None,
) -> list[ParsedSegment]:
    """从 python-docx 的 Table 提取行，再交给通用的 build_table_segments_from_rows 处理。"""
    rows: list[list[str]] = []
    for row in table.rows:
        cells = [_docx_table_cell_text(c) for c in row.cells]
        if any(cells):
            rows.append(cells)
    return build_table_segments_from_rows(rows, ti, offset_ref, parts, heading_path)


def _iter_docx_body_blocks(doc: Any):
    """按文档顺序迭代 body 中的段落与表格（保持原始 docx body 顺序）。"""
    if docx_qn is None or DocxParagraph is None or DocxTable is None:
        for p in doc.paragraphs:
            yield ("paragraph", p)
        for t in doc.tables:
            yield ("table", t)
        return
    body = doc.element.body
    p_tag = docx_qn("w:p")
    tbl_tag = docx_qn("w:tbl")
    for child in body.iterchildren():
        if child.tag == p_tag:
            yield ("paragraph", DocxParagraph(child, doc))
        elif child.tag == tbl_tag:
            yield ("table", DocxTable(child, doc))


def _parse_docx(file_bytes: bytes) -> ParsedDocument:
    if DocxDocument is None:
        raise UnsupportedDocumentError("未安装 python-docx，无法解析 .docx 文件")
    doc = DocxDocument(BytesIO(file_bytes))
    segments: list[ParsedSegment] = []
    parts: list[str] = []
    offset_ref = [0]
    heading_stack: list[tuple[str, str]] = []
    current_heading_path: str | None = None
    table_counter = 0

    for kind, node in _iter_docx_body_blocks(doc):
        if kind == "paragraph":
            t = (node.text or "").strip()
            if not t:
                continue
            style_name = None
            try:
                style_name = node.style.name if node.style is not None else None  # type: ignore[attr-defined]
            except Exception:
                style_name = None
            cls = _detect_heading_class(t, style_name)
            start = offset_ref[0]
            end = start + len(t)
            if cls is not None:
                current_heading_path = _update_heading_path(heading_stack, cls, t)
                segments.append(
                    ParsedSegment(
                        text=t,
                        start_offset=start,
                        end_offset=end,
                        heading_path=current_heading_path,
                        metadata={
                            "block": "heading",
                            "heading_class": cls,
                            "heading_level": _CLASS_ORDER.get(cls, 3),
                            "heading_path": current_heading_path,
                        },
                    )
                )
            else:
                segments.append(
                    ParsedSegment(
                        text=t,
                        start_offset=start,
                        end_offset=end,
                        heading_path=current_heading_path,
                        metadata={
                            "block": "paragraph",
                            "heading_path": current_heading_path,
                        },
                    )
                )
            parts.append(t)
            offset_ref[0] = end + 1
        elif kind == "table":
            table_segments = _docx_table_to_segments(
                node,
                table_counter,
                offset_ref,
                parts,
                current_heading_path,
            )
            segments.extend(table_segments)
            table_counter += 1

    full_text = "\n".join(parts).strip()
    if not full_text:
        return ParsedDocument(parser_type="docx", text="", char_count=0, segments=[], metadata={})
    heading_count = sum(1 for s in segments if (s.metadata or {}).get("block") == "heading")
    table_count = table_counter
    table_row_count = sum(
        1 for s in segments if (s.metadata or {}).get("block") == "table" and (s.metadata or {}).get("table_role") == "row"
    )
    return ParsedDocument(
        parser_type="docx",
        text=full_text,
        char_count=len(full_text),
        segments=segments,
        metadata={
            "paragraph_and_table_blocks": len(segments),
            "heading_count": heading_count,
            "table_count": table_count,
            "table_row_count": table_row_count,
        },
    )


def _parse_xlsx_xlsm(file_bytes: bytes, suffix: str, log: Callable[[str], None] | None = None) -> ParsedDocument:
    if load_workbook is None:
        raise UnsupportedDocumentError("未安装 openpyxl，无法解析 Excel 文档")

    def _log(msg: str) -> None:
        if log:
            log(msg)

    _log(f"Excel（{suffix}）：使用 openpyxl 只读模式打开，约 {len(file_bytes)} 字节")
    wb = load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    try:
        names = wb.sheetnames
        _log(f"工作簿共 {len(names)} 个工作表：{', '.join(names[:20])}{'…' if len(names) > 20 else ''}")
        segments: list[ParsedSegment] = []
        parts: list[str] = []
        offset = 0
        for sheet in wb:
            _log(f"工作表「{sheet.title}」：开始扫描行…")
            rows_text: list[str] = []
            row_count = 0
            nonempty_rows = 0
            for row in sheet.iter_rows(values_only=True):
                row_count += 1
                cells = [str(c).strip() if c is not None else "" for c in row]
                if not any(cells):
                    continue
                nonempty_rows += 1
                rows_text.append("\t".join(cells))
                if row_count % 5000 == 0:
                    _log(f"工作表「{sheet.title}」已扫描 {row_count} 行（其中非空 {nonempty_rows} 行）…")
            sheet_body = "\n".join(rows_text).strip()
            _log(f"工作表「{sheet.title}」：扫描结束，总行数 {row_count}，非空行 {nonempty_rows}，拼接文本长度 {len(sheet_body)}")
            if not sheet_body:
                _log(f"工作表「{sheet.title}」无有效单元格内容，跳过")
                continue
            block = f"## {sheet.title}\n{sheet_body}"
            start = offset
            end = offset + len(block)
            segments.append(
                ParsedSegment(
                    text=block,
                    start_offset=start,
                    end_offset=end,
                    heading_path=sheet.title,
                    metadata={"sheet": sheet.title},
                )
            )
            parts.append(block)
            offset = end + 2
        full_text = "\n\n".join(parts).strip()
        label = "xlsx" if suffix == "xlsx" else "xlsm"
        _log(f"Excel 解析汇总：合并文本长度 {len(full_text)}，分段数 {len(segments)}")
        return ParsedDocument(
            parser_type=label,
            text=full_text,
            char_count=len(full_text),
            segments=segments
            or [ParsedSegment(text=full_text, start_offset=0, end_offset=len(full_text), metadata={})],
            metadata={"sheet_count": len(segments)},
        )
    finally:
        wb.close()


def _parse_xls(file_bytes: bytes, log: Callable[[str], None] | None = None) -> ParsedDocument:
    if xlrd is None:
        raise UnsupportedDocumentError("未安装 xlrd，无法解析 .xls 文件")

    def _log(msg: str) -> None:
        if log:
            log(msg)

    _log(f"Excel（xls）：使用 xlrd 打开，约 {len(file_bytes)} 字节")
    book = xlrd.open_workbook(file_contents=file_bytes)
    _log(f"工作簿共 {book.nsheets} 个工作表")
    segments: list[ParsedSegment] = []
    parts: list[str] = []
    offset = 0
    for si in range(book.nsheets):
        sheet = book.sheet_by_index(si)
        _log(f"工作表「{sheet.name}」：共 {sheet.nrows} 行 × {sheet.ncols} 列，开始读取…")
        rows_text: list[str] = []
        for ri in range(sheet.nrows):
            values = sheet.row_values(ri)
            cells = [str(c).strip() if c != "" else "" for c in values]
            if not any(cells):
                continue
            rows_text.append("\t".join(cells))
            if ri > 0 and ri % 5000 == 0:
                _log(f"工作表「{sheet.name}」已读取 {ri} 行…")
        sheet_body = "\n".join(rows_text).strip()
        if not sheet_body:
            continue
        title = sheet.name
        block = f"## {title}\n{sheet_body}"
        start = offset
        end = offset + len(block)
        segments.append(
            ParsedSegment(
                text=block,
                start_offset=start,
                end_offset=end,
                heading_path=title,
                metadata={"sheet": title},
            )
        )
        parts.append(block)
        offset = end + 2
        _log(f"工作表「{sheet.name}」：有效文本长度 {len(sheet_body)}")
    full_text = "\n\n".join(parts).strip()
    _log(f"xls 解析汇总：合并文本长度 {len(full_text)}，分段数 {len(segments)}")
    return ParsedDocument(
        parser_type="xls",
        text=full_text,
        char_count=len(full_text),
        segments=segments
        or [ParsedSegment(text=full_text, start_offset=0, end_offset=len(full_text), metadata={})],
        metadata={"sheet_count": len(segments)},
    )


def _parse_csv(file_bytes: bytes) -> ParsedDocument:
    text = _decode_text_content(file_bytes)
    sio = StringIO(text)
    rows: list[str] = []
    try:
        sample = text[:4096]
        dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
    except csv.Error:
        dialect = csv.excel
    sio.seek(0)
    for row in csv.reader(sio, dialect):
        if any((c or "").strip() for c in row):
            rows.append("\t".join((c or "").strip() for c in row))
    full_text = "\n".join(rows).strip()
    segment = ParsedSegment(text=full_text, start_offset=0, end_offset=len(full_text), metadata={"block": "csv"})
    return ParsedDocument(
        parser_type="csv",
        text=full_text,
        char_count=len(full_text),
        segments=[segment],
        metadata={"row_count": len(rows)},
    )


def parse_document(
    file_name: str,
    file_bytes: bytes,
    log: Callable[[str], None] | None = None,
) -> ParsedDocument:
    def _log(msg: str) -> None:
        if log:
            log(msg)

    suffix = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    _log(f"开始解析「{file_name}」，扩展名 .{suffix or '（无）'}，大小 {len(file_bytes)} 字节")

    if suffix == "doc":
        raise UnsupportedDocumentError(
            "暂不支持旧版 Word（.doc）。请在 Word 中将文件「另存为」.docx 后再上传。"
        )

    if suffix == "docx":
        _log("使用 python-docx 解析 docx…")
        doc = _parse_docx(file_bytes)
        _log(f"docx：字符数 {doc.char_count}，分段 {len(doc.segments)}")
        return doc

    if suffix == "xlsx" or suffix == "xlsm":
        return _parse_xlsx_xlsm(file_bytes, suffix, log=log)

    if suffix == "xls":
        return _parse_xls(file_bytes, log=log)

    if suffix == "csv":
        _log("按 CSV 规则解析…")
        doc = _parse_csv(file_bytes)
        _log(f"CSV：有效数据行 {doc.metadata.get('row_count', 0)}，文本长度 {doc.char_count}")
        return doc

    if suffix == "pdf":
        doc = _parse_pdf(file_bytes, file_name=file_name, log=log)
        _log(f"PDF：字符数 {doc.char_count}，分段 {len(doc.segments)}，元数据 {doc.metadata}")
        return doc

    text = _decode_text_content(file_bytes).strip()
    if not text:
        _log("解码后文本为空")
        return ParsedDocument(parser_type=suffix or "txt", text="", char_count=0, segments=[], metadata={})

    if suffix == "md":
        segments = _build_segments_from_sections(_split_markdown_sections(text))
        _log(f"Markdown：分段数 {len(segments)}")
        return ParsedDocument(
            parser_type="md",
            text=text,
            char_count=len(text),
            segments=segments,
            metadata={"section_count": len(segments)},
        )

    segments = [
        ParsedSegment(
            text=text,
            start_offset=0,
            end_offset=len(text),
            metadata={},
        )
    ]
    _log(f"纯文本：长度 {len(text)}")
    return ParsedDocument(parser_type=suffix or "txt", text=text, char_count=len(text), segments=segments, metadata={})
