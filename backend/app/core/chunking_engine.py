from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.core.document_parser import ParsedSegment
from app.core.heading_match import heading_starts_body as _heading_starts_body
from app.core.heading_match import heading_starts_cn_section as _heading_starts_cn_section
from app.core.heading_match import is_inline_enumeration_marker as _is_inline_enumeration_marker
from app.core.heading_match import normalize_heading_match_text

_CN_NUM = r"[一二三四五六七八九十百千]+"
_ENUM_LIST_LINE = re.compile(r"^\d+\s*[、.．)）]\s*")
_CN_CHAPTER_LINE = re.compile(rf"^(?:第\s*)?{_CN_NUM}\s*[、.．]")
_CN_SECTION_LINE = re.compile(rf"^[(（]\s*{_CN_NUM}\s*[)）]")


ChunkingMode = Literal["general", "parent_child"]
ParentMode = Literal["paragraph", "full_document"]


@dataclass
class ChunkingGeneralConfig:
    delimiter: str
    max_length: int
    overlap: int
    collapse_whitespace: bool


@dataclass
class ChunkingParentChildConfig:
    parent_mode: ParentMode
    parent_delimiter: str
    parent_max_length: int
    child_delimiter: str
    child_max_length: int
    child_overlap: int
    collapse_whitespace: bool


@dataclass
class ChunkingConfig:
    mode: ChunkingMode
    general: ChunkingGeneralConfig
    parent_child: ChunkingParentChildConfig


def _unescape_delimiter(value: str) -> str:
    # 前端保存的是可见的 \\n 形式，这里转成真实换行
    return value.replace("\\r", "\r").replace("\\n", "\n").replace("\\t", "\t")


_SPACE_RE = re.compile(r"[\s\u00a0]+", re.UNICODE)
_MULTI_BLANK_LINES_RE = re.compile(r"(?:[ \t]*\n){3,}")


def _preprocess_text(text: str, *, collapse_whitespace: bool) -> str:
    t = text
    if collapse_whitespace:
        t = _SPACE_RE.sub(" ", t)
        # 保留最多两行空行，避免过度粘连
        t = _MULTI_BLANK_LINES_RE.sub("\n\n", t)
    return t.strip()


def _split_with_offsets(text: str, delimiter: str) -> list[tuple[int, int, str]]:
    if delimiter == "":
        return [(0, len(text), text)]
    out: list[tuple[int, int, str]] = []
    start = 0
    dlen = len(delimiter)
    while start <= len(text):
        idx = text.find(delimiter, start)
        if idx < 0:
            part = text[start:]
            if part.strip():
                out.append((start, len(text), part))
            break
        part = text[start:idx]
        if part.strip():
            out.append((start, idx, part))
        start = idx + dlen
    return out


def apply_general_chunking(
    *,
    segments: list[ParsedSegment],
    delimiter: str,
    collapse_whitespace: bool,
) -> list[ParsedSegment]:
    """按 delimiter 先分段（保留 offset 近似），不做长度切块（长度切块交给 text_chunker.chunk_segments）。"""
    delim = _unescape_delimiter(delimiter or "")
    out: list[ParsedSegment] = []
    for seg in segments:
        pre = _preprocess_text(seg.text, collapse_whitespace=collapse_whitespace)
        if not pre:
            continue
        if not delim:
            out.append(
                ParsedSegment(
                    text=pre,
                    start_offset=seg.start_offset,
                    end_offset=seg.start_offset + len(pre),
                    page_no=seg.page_no,
                    heading_path=seg.heading_path,
                    metadata=dict(seg.metadata or {}),
                )
            )
            continue
        # 为了保持 offset 可用，这里在“预处理后的文本”上按 delimiter 切；offset 采用原 seg.start_offset + 切片起点。
        # 这并非严格映射（因预处理可能改变长度），但可提供大致范围用于引用展示。
        for local_start, local_end, part in _split_with_offsets(pre, delim):
            part_trimmed = part.strip()
            if not part_trimmed:
                continue
            out.append(
                ParsedSegment(
                    text=part_trimmed,
                    start_offset=seg.start_offset + local_start,
                    end_offset=seg.start_offset + local_start + len(part_trimmed),
                    page_no=seg.page_no,
                    heading_path=seg.heading_path,
                    metadata=dict(seg.metadata or {}),
                )
            )
    return out


def apply_parent_child_chunking(
    *,
    segments: list[ParsedSegment],
    cfg: ChunkingParentChildConfig,
) -> list[ParsedSegment]:
    """
    父子分段：生成“子段” ParsedSegment 列表，供 text_chunker.chunk_segments 继续按 child_max_length / child_overlap 切块。
    父块信息会写入每个子段的 metadata（parent_*）。
    """
    collapse = cfg.collapse_whitespace
    parent_delim = _unescape_delimiter(cfg.parent_delimiter or "")
    child_delim = _unescape_delimiter(cfg.child_delimiter or "")

    # 构造父块文本序列
    parents: list[tuple[int, str, dict[str, Any]]] = []
    if cfg.parent_mode == "full_document":
        merged = "\n\n".join(_preprocess_text(seg.text, collapse_whitespace=collapse) for seg in segments if seg.text.strip())
        merged = merged.strip()
        if merged:
            parents.append((0, merged, {"parent_mode": "full_document"}))
    else:
        # paragraph：在每个原 segment 内做父级切分，然后再按 parent_max_length 交给后续切块（这里仅做 delimiter 切分）
        base_parent_index = 0
        for seg in segments:
            pre = _preprocess_text(seg.text, collapse_whitespace=collapse)
            if not pre:
                continue
            parts = _split_with_offsets(pre, parent_delim) if parent_delim else [(0, len(pre), pre)]
            for _, __, part in parts:
                p = part.strip()
                if not p:
                    continue
                parents.append(
                    (
                        base_parent_index,
                        p,
                        {
                            "parent_mode": "paragraph",
                            "page_no": seg.page_no,
                            "heading_path": seg.heading_path,
                        },
                    )
                )
                base_parent_index += 1

    # 从父块生成子段
    children: list[ParsedSegment] = []
    for parent_index, parent_text, parent_meta in parents:
        child_parts = _split_with_offsets(parent_text, child_delim) if child_delim else [(0, len(parent_text), parent_text)]
        parent_preview = parent_text[:400]
        for local_start, _, part in child_parts:
            c = part.strip()
            if not c:
                continue
            meta = dict(parent_meta)
            meta.update(
                {
                    "chunking_mode": "parent_child",
                    "parent_index": parent_index,
                    "parent_preview": parent_preview,
                    "parent_char_count": len(parent_text),
                    "child_local_start": local_start,
                }
            )
            children.append(
                ParsedSegment(
                    text=c,
                    start_offset=local_start,
                    end_offset=local_start + len(c),
                    page_no=parent_meta.get("page_no"),
                    heading_path=parent_meta.get("heading_path"),
                    metadata=meta,
                )
            )
    return children


def merge_leading_preamble_segments(
    segments: list[ParsedSegment],
    *,
    full_text: str | None = None,
    short_max: int = 280,
    preamble_budget: int = 1800,
    max_segments: int = 16,
) -> list[ParsedSegment]:
    """
    将文档开头连续「短段」合并为一条分段，便于后续作为一个语义单元切块（封面/页眉/主标题等）。

    Word 中页眉、密级、主标题常为多个短段落；若不合并，易出现 Chunk-1、Chunk-2 均为几十字的小块。
    合并后的段标记 metadata.block=document_preamble，与正文区分。

    若提供 full_text，则用切片拼接正文，保证与全文 offset 一致（便于预览与引用）。
    """
    if len(segments) < 2:
        return segments

    preamble: list[ParsedSegment] = []
    for seg in segments:
        meta = seg.metadata or {}
        t = seg.text.strip()
        if not t:
            continue
        if meta.get("block") == "table":
            break
        if _heading_starts_body(t):
            break
        if meta.get("block") == "heading":
            if len(t) > short_max:
                break
        projected = sum(len(x.text.strip()) for x in preamble) + len(t)
        if preamble:
            projected += len(preamble)
        if projected > preamble_budget or len(preamble) >= max_segments:
            break
        preamble.append(seg)

    if len(preamble) < 2:
        return segments

    first, last = preamble[0], preamble[-1]
    if full_text is not None and 0 <= first.start_offset <= last.end_offset <= len(full_text):
        merged_text = full_text[first.start_offset : last.end_offset]
    else:
        merged_text = "\n".join(x.text for x in preamble)

    new_meta = dict(first.metadata or {})
    new_meta["block"] = "document_preamble"
    new_meta["preamble_segment_count"] = len(preamble)

    merged = ParsedSegment(
        text=merged_text,
        start_offset=first.start_offset,
        end_offset=last.end_offset,
        page_no=first.page_no,
        heading_path=first.heading_path,
        metadata=new_meta,
    )
    k = len(preamble)
    return [merged, *segments[k:]]


def heading_path_for_merge(heading_path: str | None) -> str | None:
    """
    相邻段合并用的章节 key：按「一、二、三、」/（一）/ 第X章 等节级分组；
    忽略文档总标题栈中的上层路径，以及历史数据里误入 path 的列表项。
    """
    if not heading_path or not heading_path.strip():
        return None
    parts = [p.strip() for p in heading_path.split(" / ") if p.strip()]
    if not parts:
        return None
    section_markers: list[str] = []
    for part in parts:
        norm = normalize_heading_match_text(part)
        if _ENUM_LIST_LINE.match(norm):
            continue
        if (
            _CN_CHAPTER_LINE.match(norm)
            or _CN_SECTION_LINE.match(norm)
            or re.match(r"^第\s*\d+\s*[章节篇部条款]", norm)
        ):
            section_markers.append(norm)
    if section_markers:
        return section_markers[-1]
    filtered = [normalize_heading_match_text(p) for p in parts if not _ENUM_LIST_LINE.match(normalize_heading_match_text(p))]
    return filtered[-1] if filtered else normalize_heading_match_text(parts[-1])


def merge_adjacent_segments_by_budget(
    segments: list[ParsedSegment],
    budget: int,
    *,
    joiner: str = "\n\n",
) -> list[ParsedSegment]:
    """
    将相邻、且属于同一「分组」的 ParsedSegment 合并为更长的段，再交给 chunk_segments 按窗口切分。

    分组规则（**章节硬边界**，按以下任一字段不同即开新桶）：
    - page_no：跨页不合并
    - heading_path：跨章节不合并（docx 场景下最重要的边界）
    - block == 'heading'：标题本身作为"桶的头"，标题之前必须先 flush
    - block == 'table'：表格段不与正文段合并
    - metadata.chunking_mode / parent_index：父子分段模式下不跨父块拼子段

    注意：父子分段模式下调用方应 **跳过** 本合并，否则会抹平同一父块下按 child_delimiter 切出的子段。

    背景：chunk_segments 对每个 segment 单独滑动切块；若单段长度远小于 budget，也会单独成块；
    docx 按 Word 段落逐条产出 segment，易出现"块数≈段落数"。本函数把多段拼进同一字符预算再切，
    并在章节/标题/表格等天然边界处强制切断，避免跨章节语义混杂。
    """
    if budget < 80 or len(segments) <= 1:
        return segments

    def bucket_key(s: ParsedSegment) -> tuple[Any, ...]:
        m = s.metadata or {}
        # 同章节内允许 heading/paragraph/table 合并；合并边界用节级 key（一、二、三、），非完整 path 栈
        return (
            s.page_no,
            m.get("chunking_mode"),
            m.get("parent_index"),
            heading_path_for_merge(s.heading_path),
        )

    out: list[ParsedSegment] = []
    bucket: list[ParsedSegment] = []

    def flush() -> None:
        nonlocal bucket
        if not bucket:
            return
        if len(bucket) == 1:
            out.append(bucket[0])
        else:
            merged_text = joiner.join(x.text.strip() for x in bucket)
            first, last = bucket[0], bucket[-1]
            # 合并后的段元数据以第一段为准，但标记是合并块
            merged_meta = dict(first.metadata or {})
            merged_meta["merged_segment_count"] = len(bucket)
            indices = [
                int((s.metadata or {}).get("block_index"))
                for s in bucket
                if (s.metadata or {}).get("block_index") is not None
            ]
            if indices:
                merged_meta["block_index"] = indices[0]
                merged_meta["block_index_end"] = indices[-1]
                if len(indices) > 1:
                    merged_meta["block_indices"] = indices
            out.append(
                ParsedSegment(
                    text=merged_text,
                    start_offset=first.start_offset,
                    end_offset=last.end_offset,
                    page_no=first.page_no,
                    heading_path=first.heading_path,
                    metadata=merged_meta,
                )
            )
        bucket = []

    for seg in segments:
        piece = seg.text.strip()
        if not piece:
            continue
        meta = seg.metadata or {}
        is_heading = meta.get("block") == "heading"

        # 遇到标题：强制 flush 之前的正文，并把标题作为新桶的起点（让标题与紧跟的正文合在一起）
        if is_heading and bucket:
            flush()

        if bucket and bucket_key(seg) != bucket_key(bucket[0]):
            flush()

        if not bucket:
            if len(piece) >= budget and not is_heading:
                out.append(seg)
            else:
                bucket.append(seg)
            continue
        combined = joiner.join(s.text.strip() for s in bucket) + joiner + piece
        if len(combined) <= budget:
            bucket.append(seg)
        else:
            flush()
            if len(piece) >= budget:
                out.append(seg)
            else:
                bucket.append(seg)
    flush()
    return out if out else segments


_MINERU_ATOMIC_BLOCKS = frozenset({"table", "image", "document_preamble"})
_MINERU_NOISE_MAX_LEN = 3
_MINERU_AXIS_TICK_RE = re.compile(r"^[-]?\d+$")
_MINERU_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w.-]+\.\w+$", re.IGNORECASE)
_ODL_LAYOUT_NOISE_RE = re.compile(
    r"^(视力保护色[:：]?|网站地图|无障碍|RSS订阅|分享到[:：]?)$",
    re.IGNORECASE,
)


_MINERU_UI_OCR_MAX_ATTACH = 120
_MINERU_FORM_OCR_RE = re.compile(r"(##|<table>|是\s*/\s*否|否\s*/\s*是)", re.IGNORECASE)
_MINERU_TABLE_CONTEXT_POP_MAX = 6
_MINERU_UI_OCR_PROMPT_RE = re.compile(
    r"(请选择|请点击|点击.*按钮|下拉框|立即办理|阅读申报须知|申报须知)",
    re.IGNORECASE,
)


def _normalize_compare_text(text: str) -> str:
    return re.sub(r"\s+", "", normalize_heading_match_text(text))


def _mineru_text_block(meta: dict[str, Any]) -> bool:
    block = meta.get("block")
    return block in {None, "paragraph", "heading", "list"}


def _mineru_image_ocr_is_form_menu_noise(ocr: str) -> bool:
    if _MINERU_FORM_OCR_RE.search(ocr):
        return True
    if len(re.findall(r"是|否", ocr)) >= 8:
        return True
    axis_ticks = re.findall(r"^[-]?\d+$", ocr, flags=re.MULTILINE)
    return len(axis_ticks) >= 5


def _mineru_image_ocr_should_attach_to_step_paragraph(prev: ParsedSegment, image: ParsedSegment) -> bool:
    ocr = (image.text or "").strip()
    if not ocr or not _mineru_image_ocr_is_form_menu_noise(ocr):
        return False
    prev_meta = prev.metadata or {}
    if not _mineru_text_block(prev_meta):
        return False
    prev_hp = (prev.heading_path or "").strip()
    img_hp = (image.heading_path or "").strip()
    if prev_hp and img_hp and prev_hp != img_hp:
        return False
    return True


def _mineru_image_ocr_should_attach_to_previous(prev: ParsedSegment, image: ParsedSegment) -> bool:
    ocr = (image.text or "").strip()
    if not ocr:
        return False
    prev_meta = prev.metadata or {}
    if not _mineru_text_block(prev_meta):
        return False
    if len(ocr) <= 48 and _MINERU_UI_OCR_PROMPT_RE.search(ocr):
        return True
    if len(ocr) <= 40 and ocr.rstrip().endswith(("：", ":", "。")):
        return True
    if len(ocr) <= _MINERU_UI_OCR_MAX_ATTACH and _MINERU_UI_OCR_PROMPT_RE.search(ocr):
        return True
    return False


def _mineru_image_ocr_is_duplicate_of_recent(ocr: str, recent: list[ParsedSegment], *, window: int = 5) -> bool:
    norm_ocr = _normalize_compare_text(ocr)
    if len(norm_ocr) < 24:
        return False
    for seg in recent[-window:]:
        meta = seg.metadata or {}
        if meta.get("block") == "image":
            continue
        norm_prev = _normalize_compare_text(seg.text)
        if not norm_prev:
            continue
        if norm_ocr in norm_prev or norm_prev in norm_ocr:
            return True
        shorter, longer = (norm_ocr, norm_prev) if len(norm_ocr) <= len(norm_prev) else (norm_prev, norm_ocr)
        if len(shorter) >= 80 and len(longer) > 0 and len(shorter) / len(longer) > 0.6:
            # 长 OCR 与近期正文高度重合（常见于截图重复「申报须知」）
            overlap = sum(1 for i in range(len(shorter) - 7) if shorter[i : i + 8] in longer)
            if overlap >= max(3, len(shorter) // 12):
                return True
    return False


def _attach_image_text_to_segment(prev: ParsedSegment, image: ParsedSegment) -> ParsedSegment:
    ocr = (image.text or "").strip()
    merged_text = prev.text.rstrip() + "\n\n" + ocr
    meta = dict(prev.metadata or {})
    meta["image_ocr_attached"] = int(meta.get("image_ocr_attached") or 0) + 1
    meta["chunk_role"] = "step_with_ocr"
    meta["retrieval_policy"] = "normal"
    img_path = (image.metadata or {}).get("img_path")
    if img_path:
        paths = list(meta.get("attached_image_paths") or [])
        paths.append(img_path)
        meta["attached_image_paths"] = paths
    return ParsedSegment(
        text=merged_text,
        start_offset=prev.start_offset,
        end_offset=prev.end_offset,
        page_no=prev.page_no,
        heading_path=prev.heading_path,
        metadata=meta,
    )


def _mineru_last_text_segment_for_image_attach(segments: list[ParsedSegment]) -> ParsedSegment | None:
    for seg in reversed(segments):
        meta = seg.metadata or {}
        if meta.get("block") == "image":
            continue
        if _mineru_text_block(meta):
            return seg
    return None


def _mineru_tag_standalone_image_segment(seg: ParsedSegment) -> ParsedSegment:
    meta = dict(seg.metadata or {})
    meta["chunk_role"] = "image_ocr"
    meta["retrieval_policy"] = "exclude_by_default"
    return ParsedSegment(
        text=seg.text,
        start_offset=seg.start_offset,
        end_offset=seg.end_offset,
        page_no=seg.page_no,
        heading_path=seg.heading_path,
        metadata=meta,
    )


def consolidate_mineru_image_segments(segments: list[ParsedSegment]) -> list[ParsedSegment]:
    """
    MinerU/ODL 图片 OCR 整理：
    - 短 UI 提示并入上一段正文（避免 orphan 块）；
    - 与近期正文高度重复的长 OCR（如截图申报须知）丢弃。
    """
    if not segments:
        return segments
    out: list[ParsedSegment] = []
    for seg in segments:
        meta = seg.metadata or {}
        if meta.get("block") != "image":
            out.append(seg)
            continue
        ocr = (seg.text or "").strip()
        if not ocr:
            continue
        attach_target = _mineru_last_text_segment_for_image_attach(out)
        if attach_target is not None and _mineru_image_ocr_should_attach_to_previous(attach_target, seg):
            idx = out.index(attach_target)
            out[idx] = _attach_image_text_to_segment(attach_target, seg)
            continue
        if attach_target is not None and _mineru_image_ocr_should_attach_to_step_paragraph(attach_target, seg):
            idx = out.index(attach_target)
            out[idx] = _attach_image_text_to_segment(attach_target, seg)
            continue
        if _mineru_image_ocr_is_duplicate_of_recent(ocr, out):
            continue
        out.append(_mineru_tag_standalone_image_segment(seg))
    return out


def mineru_text_is_layout_noise(text: str) -> bool:
    """MinerU / OpenDataLoader PDF layout 碎片：单字、坐标轴刻度、封面邮箱、站点导航等。"""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return True
    if len(t) == 1:
        return True
    if len(t) <= _MINERU_NOISE_MAX_LEN and _MINERU_AXIS_TICK_RE.match(t):
        return True
    if len(t) <= 32 and _MINERU_EMAIL_RE.fullmatch(t):
        return True
    if _ODL_LAYOUT_NOISE_RE.match(t):
        return True
    if len(t) <= 48 and re.search(r"(当前位置|您现在所在的位置|您现在的位置)", t):
        return True
    if len(t) <= 36 and re.fullmatch(r"(首页(\s+\S+){1,6})", t):
        return True
    return False


def mineru_merged_text_is_retrievable(text: str) -> bool:
    """合并后若仍全是 layout 噪声，则不入库。"""
    t = (text or "").strip()
    if not t:
        return False
    if len(t) > 24:
        return True
    lines = [ln.strip() for ln in re.split(r"[\n\r]+", t) if ln.strip()]
    if not lines:
        return False
    return any(not mineru_text_is_layout_noise(ln) for ln in lines)


def mineru_segment_is_atomic(segment: ParsedSegment) -> bool:
    """MinerU 索引阶段不可与正文合并的段（表格/图片/文前）。"""
    meta = segment.metadata or {}
    if meta.get("block") in _MINERU_ATOMIC_BLOCKS:
        return True
    if meta.get("block") == "table" or meta.get("table_role"):
        return True
    return False


def _mineru_bucket_all_headings(bucket: list[ParsedSegment]) -> bool:
    return bool(bucket) and all((s.metadata or {}).get("block") == "heading" for s in bucket)


def _mineru_bucket_is_table_context(bucket: list[ParsedSegment]) -> bool:
    """桶内为标题或极短说明，适合并入紧随其后的表格/图片。"""
    if not bucket:
        return False
    for seg in bucket:
        meta = seg.metadata or {}
        block = meta.get("block")
        if block == "heading":
            continue
        if block in {None, "paragraph"} and len(seg.text.strip()) <= 120:
            continue
        return False
    return True


def _mineru_segment_is_table_context_candidate(seg: ParsedSegment) -> bool:
    meta = seg.metadata or {}
    if meta.get("mineru_section_merge"):
        return False
    text = (seg.text or "").strip()
    if not text:
        return False
    if _heading_starts_cn_section(text):
        return False
    block = meta.get("block")
    if block == "heading":
        return len(text) <= 120
    if block in {None, "paragraph"} and len(text) <= 120:
        return True
    return False


def _mineru_pop_table_context_from_out(
    out: list[ParsedSegment],
    table: ParsedSegment,
) -> list[ParsedSegment]:
    ctx: list[ParsedSegment] = []
    while out and len(ctx) < _MINERU_TABLE_CONTEXT_POP_MAX:
        prev = out[-1]
        if table.page_no is not None and prev.page_no != table.page_no:
            break
        if not _mineru_segment_is_table_context_candidate(prev):
            break
        ctx.insert(0, out.pop())
    return ctx


def _mineru_context_already_in_table(table: ParsedSegment, ctx: list[ParsedSegment]) -> bool:
    body = (table.text or "").strip()
    if not body or not ctx:
        return False
    hits = sum(1 for seg in ctx if seg.text.strip() and seg.text.strip() in body)
    return hits >= max(1, (len(ctx) + 1) // 2)


def _mineru_attach_table_context(
    out: list[ParsedSegment],
    bucket: list[ParsedSegment],
    atomic: ParsedSegment,
    *,
    joiner: str,
) -> tuple[list[ParsedSegment], ParsedSegment]:
    ctx = bucket if _mineru_bucket_is_table_context(bucket) else []
    atomic_block = (atomic.metadata or {}).get("block")
    if not ctx and atomic_block == "table":
        ctx = _mineru_pop_table_context_from_out(out, atomic)
    if not ctx:
        return bucket, atomic
    if _mineru_context_already_in_table(atomic, ctx):
        return [], atomic
    return [], _mineru_merge_context_into_atomic(ctx, atomic, joiner=joiner)


def _mineru_merge_context_into_atomic(
    bucket: list[ParsedSegment],
    atomic: ParsedSegment,
    *,
    joiner: str,
) -> ParsedSegment:
    context_parts = [x.text.strip() for x in bucket if x.text.strip()]
    atomic_text = atomic.text.strip()
    merged_text = joiner.join(context_parts + [atomic_text]) if context_parts else atomic_text
    first = bucket[0] if bucket else atomic
    merged_meta = dict(atomic.metadata or {})
    merged_meta["mineru_context_merged"] = True
    merged_meta["context_segment_count"] = len(bucket)
    if context_parts:
        merged_meta["table_context_prefix"] = joiner.join(context_parts)
    if bucket:
        indices = [
            int((s.metadata or {}).get("block_index"))
            for s in bucket
            if (s.metadata or {}).get("block_index") is not None
        ]
        if indices:
            merged_meta["context_block_index_start"] = indices[0]
            merged_meta["context_block_index_end"] = indices[-1]
    return ParsedSegment(
        text=merged_text,
        start_offset=first.start_offset,
        end_offset=atomic.end_offset,
        page_no=atomic.page_no if atomic.page_no is not None else first.page_no,
        heading_path=atomic.heading_path or first.heading_path,
        metadata=merged_meta,
    )


def merge_mineru_segments_by_section(
    segments: list[ParsedSegment],
    budget: int,
    *,
    joiner: str = "\n\n",
    respect_page_boundary: bool = True,
) -> list[ParsedSegment]:
    """
    MinerU 正文段按 heading_path + 字符预算合并；图片/表格保持原子块。

    PDF 研报建议 respect_page_boundary=False，允许同一章节跨页合并。
    layout 噪声段尽量并入相邻正文，合并后仍全为噪声则丢弃。
    """
    if budget < 80 or len(segments) <= 1:
        return segments

    out: list[ParsedSegment] = []
    bucket: list[ParsedSegment] = []

    def bucket_key(s: ParsedSegment) -> tuple[Any, ...]:
        if respect_page_boundary:
            return (s.page_no, heading_path_for_merge(s.heading_path))
        return (heading_path_for_merge(s.heading_path),)

    def emit_segment(seg: ParsedSegment) -> None:
        if mineru_merged_text_is_retrievable(seg.text):
            out.append(seg)

    def flush_bucket() -> None:
        nonlocal bucket
        if not bucket:
            return
        if len(bucket) == 1:
            emit_segment(bucket[0])
        else:
            merged_text = joiner.join(x.text.strip() for x in bucket if x.text.strip())
            if not mineru_merged_text_is_retrievable(merged_text):
                bucket = []
                return
            first, last = bucket[0], bucket[-1]
            merged_meta = dict(first.metadata or {})
            merged_meta["merged_segment_count"] = len(bucket)
            merged_meta["mineru_section_merge"] = True
            out.append(
                ParsedSegment(
                    text=merged_text,
                    start_offset=first.start_offset,
                    end_offset=last.end_offset,
                    page_no=first.page_no,
                    heading_path=first.heading_path,
                    metadata=merged_meta,
                )
            )
        bucket = []

    for seg in segments:
        if mineru_segment_is_atomic(seg):
            bucket, merged_table = _mineru_attach_table_context(out, bucket, seg, joiner=joiner)
            if bucket:
                flush_bucket()
            out.append(merged_table)
            continue

        piece = seg.text.strip()
        if not piece:
            continue

        meta = seg.metadata or {}
        is_noise = mineru_text_is_layout_noise(piece)

        if (
            meta.get("block") == "heading"
            and bucket
            and not is_noise
            and _heading_starts_cn_section(piece)
        ):
            flush_bucket()

        if bucket and bucket_key(seg) != bucket_key(bucket[0]):
            same_page = seg.page_no == bucket[0].page_no
            heading_chain = (
                _mineru_bucket_all_headings(bucket)
                and meta.get("block") == "heading"
                and same_page
            )
            if not heading_chain:
                flush_bucket()

        if is_noise and not bucket:
            bucket.append(seg)
            continue

        if not bucket:
            if len(piece) >= budget and meta.get("block") != "heading" and not is_noise:
                emit_segment(seg)
            else:
                bucket.append(seg)
            continue

        combined = joiner.join(s.text.strip() for s in bucket if s.text.strip()) + joiner + piece
        if len(combined) <= budget:
            bucket.append(seg)
        else:
            flush_bucket()
            if len(piece) >= budget and meta.get("block") != "heading" and not is_noise:
                emit_segment(seg)
            else:
                bucket.append(seg)

    flush_bucket()
    if out:
        return out
    # 合并后无有效正文：丢弃纯 layout 噪声，保留原子块（表格/图片）
    retained: list[ParsedSegment] = []
    for seg in segments:
        if mineru_segment_is_atomic(seg):
            retained.append(seg)
        elif mineru_merged_text_is_retrievable(seg.text.strip()):
            retained.append(seg)
    return retained


def structured_parser_should_merge_sections(*, parser_type: str, parser_backend: str | None) -> bool:
    """MinerU / OpenDataLoader 结构化 Office/PDF 按章节合并后再入库。

    OpenDataLoader 仅作为 PDF 引擎（见 parser_config.PDF_ENGINES / DOCX_ENGINES），
    不产出 docx/pptx，故仅对 pdf 生效；MinerU 为多格式引擎，覆盖 Office + PDF。
    """
    if parser_backend == "opendataloader":
        return parser_type == "pdf"
    if parser_backend == "mineru":
        return parser_type in {"docx", "pptx", "ppt", "pdf", "mineru"}
    return False


def _clone_segment_with_text(
    seg: ParsedSegment,
    text: str,
    *,
    meta_override: dict[str, Any] | None = None,
) -> ParsedSegment:
    meta = dict(seg.metadata or {})
    if meta_override:
        meta.update(meta_override)
    trimmed = text.strip()
    return ParsedSegment(
        text=trimmed,
        start_offset=seg.start_offset,
        end_offset=seg.end_offset,
        page_no=seg.page_no,
        heading_path=meta.get("heading_path", seg.heading_path),
        metadata=meta,
    )


def _split_text_into_cn_section_blocks(text: str) -> list[str]:
    """按行识别「一、二、三、」节标题切分文本块（兼容单换行合并段）。"""
    stripped = (text or "").strip()
    if not stripped:
        return []
    lines = stripped.split("\n")
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        piece = line.strip()
        prev_piece = current[-1].strip() if current else None
        if (
            piece
            and _heading_starts_cn_section(piece)
            and current
            and not _is_inline_enumeration_marker(piece, prev_piece)
        ):
            block = "\n".join(current).strip()
            if block:
                blocks.append(block)
            current = [line]
        else:
            current.append(line)
    if current:
        block = "\n".join(current).strip()
        if block:
            blocks.append(block)
    if len(blocks) <= 1:
        parts = [p.strip() for p in re.split(r"\n\n+", stripped) if p.strip()]
        if len(parts) > 1:
            return parts
    return blocks


def _split_one_segment_at_section_headings(seg: ParsedSegment, *, joiner: str = "\n\n") -> list[ParsedSegment]:
    """若合并段内出现多个「一、二、三、」节标题，拆回一节一块（含误并入文前的正文）。"""
    meta = seg.metadata or {}
    if meta.get("block") in {"table", "image"} or meta.get("table_role"):
        if not meta.get("mineru_context_merged"):
            return [seg]
    text = (seg.text or "").strip()
    if not text:
        return [seg]
    parts = _split_text_into_cn_section_blocks(text)
    if len(parts) <= 1:
        return [seg]
    section_starts: list[int] = []
    for i, p in enumerate(parts):
        first_line = p.split("\n", 1)[0].strip()
        prev_first = parts[i - 1].split("\n", 1)[0].strip() if i > 0 else None
        if _heading_starts_cn_section(first_line) and not _is_inline_enumeration_marker(first_line, prev_first):
            section_starts.append(i)
    if not section_starts or len(section_starts) <= 1:
        return [seg]

    result: list[ParsedSegment] = []
    if section_starts[0] > 0:
        prefix = joiner.join(parts[: section_starts[0]])
        prefix_meta = dict(meta)
        if meta.get("block") == "document_preamble":
            prefix_meta["block"] = "document_preamble"
        else:
            prefix_meta["block"] = "paragraph"
        prefix_meta["split_from_merged"] = True
        result.append(_clone_segment_with_text(seg, prefix, meta_override=prefix_meta))

    for idx, start in enumerate(section_starts):
        end = section_starts[idx + 1] if idx + 1 < len(section_starts) else len(parts)
        chunk_text = joiner.join(parts[start:end])
        section_title = normalize_heading_match_text(parts[start])
        chunk_meta = dict(meta)
        chunk_meta["split_from_merged"] = True
        chunk_meta["heading_path"] = section_title
        chunk_meta["block"] = "paragraph"
        chunk_meta.pop("preamble_segment_count", None)
        result.append(_clone_segment_with_text(seg, chunk_text, meta_override=chunk_meta))
    return result or [seg]


def split_segments_at_cn_section_headings(
    segments: list[ParsedSegment],
    *,
    joiner: str = "\n\n",
) -> list[ParsedSegment]:
    """合并后安全网：避免多节挤在同一块（如 565 字含一～四节）。"""
    if len(segments) <= 1:
        split = _split_one_segment_at_section_headings(segments[0], joiner=joiner) if segments else segments
    else:
        out: list[ParsedSegment] = []
        for seg in segments:
            out.extend(_split_one_segment_at_section_headings(seg, joiner=joiner))
        split = out
    split = merge_orphan_document_title_with_next(split, joiner=joiner)
    return merge_orphan_section_heading_with_next(split, joiner=joiner)


_DOC_TITLE_MERGE_MAX_LEN = 120


def _is_orphan_document_title_segment(seg: ParsedSegment, *, max_title_len: int = _DOC_TITLE_MERGE_MAX_LEN) -> bool:
    """文档总标题（非「一、二、三、」节标题）单独成段时，检索价值低且易误命中。"""
    meta = seg.metadata or {}
    if meta.get("block") in _MINERU_ATOMIC_BLOCKS or meta.get("table_role"):
        return False
    text = normalize_heading_match_text((seg.text or "").strip())
    if not text or len(text) > max_title_len:
        return False
    if _heading_starts_cn_section(text) or _heading_starts_body(text):
        return False
    if text.count("\n") >= 2:
        return False
    return True


def merge_orphan_document_title_with_next(
    segments: list[ParsedSegment],
    *,
    joiner: str = "\n\n",
    max_title_len: int = _DOC_TITLE_MERGE_MAX_LEN,
) -> list[ParsedSegment]:
    """将单独成段的文档总标题并入下一段，避免标题-only chunk 干扰检索。"""
    if len(segments) < 2:
        return segments
    out: list[ParsedSegment] = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        if i + 1 < len(segments) and _is_orphan_document_title_segment(seg, max_title_len=max_title_len):
            nxt = segments[i + 1]
            nxt_meta = nxt.metadata or {}
            if nxt_meta.get("block") not in _MINERU_ATOMIC_BLOCKS and not nxt_meta.get("table_role"):
                merged_text = joiner.join([seg.text.strip(), nxt.text.strip()])
                merged_meta = dict(nxt_meta)
                merged_meta["merged_document_title"] = normalize_heading_match_text(seg.text.strip())
                merged_meta["merged_segment_count"] = int(merged_meta.get("merged_segment_count") or 1) + 1
                out.append(
                    ParsedSegment(
                        text=merged_text.strip(),
                        start_offset=seg.start_offset,
                        end_offset=nxt.end_offset,
                        page_no=nxt.page_no if nxt.page_no is not None else seg.page_no,
                        heading_path=nxt.heading_path or seg.heading_path,
                        metadata=merged_meta,
                    )
                )
                i += 2
                continue
        out.append(seg)
        i += 1
    return out


_SECTION_HEADING_MERGE_MAX_LEN = 120
_SECTION_HEADING_BODY_LINE_MIN = 24


def _is_orphan_section_heading_segment(
    seg: ParsedSegment,
    *,
    max_len: int = _SECTION_HEADING_MERGE_MAX_LEN,
    body_line_min: int = _SECTION_HEADING_BODY_LINE_MIN,
) -> bool:
    """纯标题块：block=heading 且仅含短标题行（无正文/列表项），检索价值低且易误命中。

    与 `merge_orphan_document_title_with_next` 互补：后者只处理「文档总标题」，
    本函数覆盖节级标题（第X章/节、一、、（一）…）以及多标题链（如「第三章 刑罚」+「第一节 …」）。

    判定为「纯标题块」需同时满足：
    - metadata.block == "heading"（解析/合并阶段判定为标题主导块）；
    - 非表格/图片原子块；
    - 归一化全文长度 <= max_len（标题通常很短）；
    - 不含正文行：任一行长度 >= body_line_min（长句正文）或为数字列表项（1、2、）即视为含正文。
    """
    meta = seg.metadata or {}
    if meta.get("block") != "heading":
        return False
    if meta.get("block") in _MINERU_ATOMIC_BLOCKS or meta.get("table_role"):
        return False
    text = (seg.text or "").strip()
    if not text:
        return False
    norm = normalize_heading_match_text(text)
    if not norm or len(norm) > max_len:
        return False
    for raw_line in norm.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if len(line) >= body_line_min:
            return False
        if _ENUM_LIST_LINE.match(line):
            return False
    return True


def merge_orphan_section_heading_with_next(
    segments: list[ParsedSegment],
    *,
    joiner: str = "\n\n",
    max_heading_len: int = _SECTION_HEADING_MERGE_MAX_LEN,
) -> list[ParsedSegment]:
    """将单独成段的「纯标题块」向下并入同节正文，避免标题-only chunk 干扰检索。

    连续多个纯标题块（章 + 节 + 小节标题链）会一起并入随后的首个正文段；
    若标题块之后紧跟表格/图片原子块或文档结尾，则保持原样（由表格上下文合并等逻辑处理）。
    """
    if len(segments) < 2:
        return segments
    out: list[ParsedSegment] = []
    n = len(segments)
    i = 0
    while i < n:
        seg = segments[i]
        if not _is_orphan_section_heading_segment(seg, max_len=max_heading_len):
            out.append(seg)
            i += 1
            continue
        j = i
        headings: list[ParsedSegment] = []
        while j < n and _is_orphan_section_heading_segment(segments[j], max_len=max_heading_len):
            headings.append(segments[j])
            j += 1
        if j < n:
            nxt = segments[j]
            nxt_meta = nxt.metadata or {}
            if nxt_meta.get("block") not in _MINERU_ATOMIC_BLOCKS and not nxt_meta.get("table_role"):
                parts = [h.text.strip() for h in headings if h.text.strip()]
                parts.append(nxt.text.strip())
                merged_text = joiner.join(p for p in parts if p)
                first = headings[0]
                merged_meta = dict(nxt_meta)
                merged_meta["merged_section_heading"] = joiner.join(
                    normalize_heading_match_text(h.text.strip()) for h in headings if h.text.strip()
                )
                merged_meta["merged_segment_count"] = (
                    int(merged_meta.get("merged_segment_count") or 1) + len(headings)
                )
                out.append(
                    ParsedSegment(
                        text=merged_text,
                        start_offset=first.start_offset,
                        end_offset=nxt.end_offset,
                        page_no=nxt.page_no if nxt.page_no is not None else first.page_no,
                        heading_path=nxt.heading_path or first.heading_path,
                        metadata=merged_meta,
                    )
                )
                i = j + 1
                continue
        # 后继为原子块或文档结尾：保留标题块，不强行合并
        out.extend(headings)
        i = j
    return out


def mineru_should_merge_sections(*, parser_type: str, parser_backend: str | None) -> bool:
    return structured_parser_should_merge_sections(parser_type=parser_type, parser_backend=parser_backend)


def mineru_office_should_merge_sections(*, parser_type: str, parser_backend: str | None) -> bool:
    """兼容旧名。"""
    return mineru_should_merge_sections(parser_type=parser_type, parser_backend=parser_backend)


def prepare_mineru_prebuilt_segments(
    segments: list[ParsedSegment],
    budget: int,
    *,
    parser_type: str,
    parser_backend: str | None,
) -> tuple[list[ParsedSegment], str | None]:
    """
    MinerU 预构建分段：Office/PDF 按章节合并 + 噪声过滤；其余类型原样返回。
    返回 (segments, log_message)。
    """
    if not structured_parser_should_merge_sections(parser_type=parser_type, parser_backend=parser_backend):
        return segments, None
    respect_page = parser_type not in {"pdf", "mineru"}
    n_before = len(segments)
    merged = merge_mineru_segments_by_section(
        segments,
        budget,
        respect_page_boundary=respect_page,
    )
    n_merged = len(merged)
    merged = split_segments_at_cn_section_headings(merged, joiner="\n\n")
    engine_label = "OpenDataLoader" if parser_backend == "opendataloader" else "MinerU"
    if len(merged) < n_before:
        page_hint = "跨页按章节" if not respect_page else "同页按章节"
        split_hint = f"；节标题硬切 {n_merged}→{len(merged)}" if len(merged) != n_merged else ""
        return merged, (
            f"{engine_label} {parser_type} 文本段按章节合并：{n_before} → {len(merged)}"
            f"（字符预算={budget}；{page_hint}；图片/表格独立；已过滤 layout 噪声{split_hint}）"
        )
    if len(merged) != n_merged:
        return merged, (
            f"{engine_label} {parser_type}：节标题硬切 {n_merged} → {len(merged)}，"
            "图片/表格保持原子块"
        )
    return merged, f"{engine_label} {parser_type}：图片/表格保持原子块，文本段已整理并过滤 layout 噪声"


def adapt_chunk_size_for_small_doc(
    segments: list[ParsedSegment],
    chunk_size: int,
    chunk_overlap: int,
    *,
    min_chunks: int = 4,
    min_chunk_size: int = 160,
) -> tuple[int, int]:
    """
    小文档自适应：当全文字符数远小于 chunk_size 时，按 min_chunks 缩小有效 chunk_size，
    保证即使是短文档也至少切出 min_chunks 个块，避免出现"全文就是一个块"的情况。

    同时按比例等比缩减 chunk_overlap（至少 0）。
    不会增大 chunk_size，只在需要时缩小；最小不低于 min_chunk_size。
    """
    total_chars = sum(len(s.text.strip()) for s in segments)
    if total_chars <= 0 or chunk_size <= min_chunk_size:
        return chunk_size, chunk_overlap
    target = max(min_chunk_size, total_chars // max(min_chunks, 1))
    if target >= chunk_size:
        return chunk_size, chunk_overlap
    ratio = target / chunk_size
    new_overlap = max(0, min(int(chunk_overlap * ratio), target - 1))
    return target, new_overlap


def parse_chunking_config(config: dict | None, *, fallback_chunk_size: int, fallback_overlap: int) -> ChunkingConfig:
    cfg = config or {}
    chunking = cfg.get("chunking") if isinstance(cfg, dict) else None
    chunking = chunking if isinstance(chunking, dict) else {}

    mode: ChunkingMode = "general" if chunking.get("mode") != "parent_child" else "parent_child"

    general_raw = chunking.get("general") if isinstance(chunking.get("general"), dict) else {}
    pc_raw = chunking.get("parent_child") if isinstance(chunking.get("parent_child"), dict) else {}

    general = ChunkingGeneralConfig(
        delimiter=str(general_raw.get("delimiter") or "\\n\\n"),
        max_length=int(general_raw.get("max_length") or fallback_chunk_size),
        overlap=int(general_raw.get("overlap") or fallback_overlap),
        collapse_whitespace=bool(general_raw.get("collapse_whitespace")) if "collapse_whitespace" in general_raw else True,
    )

    pc_parent_mode: ParentMode = "full_document" if pc_raw.get("parent_mode") == "full_document" else "paragraph"
    parent_child = ChunkingParentChildConfig(
        parent_mode=pc_parent_mode,
        parent_delimiter=str(pc_raw.get("parent_delimiter") or "\\n\\n"),
        parent_max_length=int(pc_raw.get("parent_max_length") or 1024),
        child_delimiter=str(pc_raw.get("child_delimiter") or "\\n"),
        child_max_length=int(pc_raw.get("child_max_length") or fallback_chunk_size),
        child_overlap=int(pc_raw.get("child_overlap") or fallback_overlap),
        collapse_whitespace=bool(pc_raw.get("collapse_whitespace")) if "collapse_whitespace" in pc_raw else True,
    )

    return ChunkingConfig(mode=mode, general=general, parent_child=parent_child)

