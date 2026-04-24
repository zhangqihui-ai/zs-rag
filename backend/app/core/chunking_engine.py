from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.core.document_parser import ParsedSegment


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
        # 遇到表格或正文标题（章节/小节）即停止：preamble 仅覆盖正文前的封面/抬头
        if meta.get("block") in {"table", "heading"}:
            break
        t = seg.text.strip()
        if not t:
            continue
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
    if budget < 200 or len(segments) <= 1:
        return segments

    def bucket_key(s: ParsedSegment) -> tuple[Any, ...]:
        m = s.metadata or {}
        # 同章节内允许 heading/paragraph/table 合并，保留以下硬边界：
        # - 跨页
        # - 跨章节 (heading_path)
        # - 父子分段模式下的父块边界
        return (
            s.page_no,
            m.get("chunking_mode"),
            m.get("parent_index"),
            s.heading_path,
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

