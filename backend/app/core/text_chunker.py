from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.document_parser import ParsedSegment


@dataclass
class ChunkCandidate:
    content: str
    chunk_index: int
    start_offset: int | None
    end_offset: int | None
    page_no: int | None = None
    heading_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    enrichment_keyword_text: str | None = None

    @property
    def char_count(self) -> int:
        return len(self.content)

    @property
    def content_preview(self) -> str:
        return self.content[:300]


_BREAK_TOKEN_TIERS: list[list[str]] = [
    ["\n\n"],
    ["\n"],
    ["。", "！", "？", "!", "?", ". "],
    ["；", ";"],
    ["，", ",", "、"],
    [" "],
]


def _choose_chunk_end(text: str, start: int, chunk_size: int) -> int:
    tentative_end = min(len(text), start + chunk_size)
    if tentative_end >= len(text):
        return len(text)

    search_from = min(len(text), start + max(chunk_size // 2, 1))
    for tier in _BREAK_TOKEN_TIERS:
        best_break = -1
        for token in tier:
            idx = text.rfind(token, search_from, tentative_end)
            if idx > best_break:
                best_break = idx
        if best_break > start:
            return best_break + 1
    return tentative_end


def _trim_content(raw: str, base_start: int) -> tuple[str, int, int]:
    left_trimmed = raw.lstrip()
    right_trimmed = left_trimmed.rstrip()
    left_trim = len(raw) - len(left_trimmed)
    total_trimmed = len(raw) - len(right_trimmed)
    start_offset = base_start + left_trim
    end_offset = base_start + len(raw) - max(total_trimmed - left_trim, 0)
    return right_trimmed, start_offset, end_offset


def segments_to_chunk_candidates(segments: list[ParsedSegment]) -> list[ChunkCandidate]:
    """解析阶段已按表格行/批切好段，直接 1:1 映射为索引块，避免二次切块膨胀。"""
    chunks: list[ChunkCandidate] = []
    for idx, segment in enumerate(segments):
        text = segment.text
        if not text.strip():
            continue
        metadata = dict(segment.metadata or {})
        if segment.page_no is not None:
            metadata.setdefault("page_no", segment.page_no)
        if segment.heading_path:
            metadata.setdefault("heading_path", segment.heading_path)
        chunks.append(
            ChunkCandidate(
                content=text.strip(),
                chunk_index=idx,
                start_offset=segment.start_offset,
                end_offset=segment.end_offset,
                page_no=segment.page_no,
                heading_path=segment.heading_path,
                metadata=metadata,
            )
        )
    for i, ch in enumerate(chunks):
        ch.chunk_index = i
    return chunks


def segment_has_atomic_blocks(segments: list[ParsedSegment]) -> bool:
    return any(_segment_is_atomic_for_chunking(s) for s in segments)


def _segment_is_atomic_for_chunking(segment: ParsedSegment) -> bool:
    """表格整段、文档抬头、MinerU 图片 OCR 等解析阶段已语义完整的段，不再按长度/overlap 二次切分。"""
    meta = segment.metadata or {}
    if meta.get("block") in {"table", "document_preamble", "image"}:
        return True
    return False


def chunk_segments(segments: list[ParsedSegment], chunk_size: int, chunk_overlap: int) -> list[ChunkCandidate]:
    chunks: list[ChunkCandidate] = []
    next_index = 0

    for segment in segments:
        text = segment.text
        if not text.strip():
            continue

        if _segment_is_atomic_for_chunking(segment):
            content, content_start, content_end = _trim_content(text, segment.start_offset or 0)
            if content:
                metadata = dict(segment.metadata or {})
                if segment.page_no is not None:
                    metadata.setdefault("page_no", segment.page_no)
                if segment.heading_path:
                    metadata.setdefault("heading_path", segment.heading_path)
                chunks.append(
                    ChunkCandidate(
                        content=content,
                        chunk_index=next_index,
                        start_offset=content_start,
                        end_offset=content_end,
                        page_no=segment.page_no,
                        heading_path=segment.heading_path,
                        metadata=metadata,
                    )
                )
                next_index += 1
            continue

        start = 0
        while start < len(text):
            end = _choose_chunk_end(text, start, chunk_size)
            if end <= start:
                end = min(len(text), start + chunk_size)
            raw_content = text[start:end]
            content, content_start, content_end = _trim_content(raw_content, segment.start_offset + start)
            if content:
                metadata = dict(segment.metadata or {})
                if segment.page_no is not None:
                    metadata.setdefault("page_no", segment.page_no)
                if segment.heading_path:
                    metadata.setdefault("heading_path", segment.heading_path)
                chunks.append(
                    ChunkCandidate(
                        content=content,
                        chunk_index=next_index,
                        start_offset=content_start,
                        end_offset=content_end,
                        page_no=segment.page_no,
                        heading_path=segment.heading_path,
                        metadata=metadata,
                    )
                )
                next_index += 1

            if end >= len(text):
                break
            start = max(end - chunk_overlap, start + 1)

    return chunks
