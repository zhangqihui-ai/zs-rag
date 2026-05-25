from __future__ import annotations

import hashlib
import json
import queue
import threading
from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.document_parser import (
    ParsedSegment,
    UnsupportedDocumentError,
    parse_document,
    validate_parsed_document_for_indexing,
)
from app.db.session import SessionLocal
from app.core.embedding_gateway import generate_embeddings
from app.core.chunking_engine import (
    apply_general_chunking,
    apply_parent_child_chunking,
    adapt_chunk_size_for_small_doc,
    merge_adjacent_segments_by_budget,
    merge_leading_preamble_segments,
    parse_chunking_config,
)
from app.core.errors import AppError
from app.core.milvus_client import create_collection_if_not_exists, delete_vectors, drop_collection_if_exists, insert_vectors
from app.core.text_chunker import ChunkCandidate, chunk_segments
from app.models.knowledge_base import (
    KnowledgeBase,
    KnowledgeBaseType,
    KnowledgeChunk,
    KnowledgeChunkVectorStatus,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
)
from app.core.kb_type import is_lightrag_kb
from app.services.knowledge_base_service import (
    ensure_knowledge_base_milvus_fields,
    format_ai_model_for_log,
    get_embedding_model_for_knowledge_base,
    get_knowledge_base_or_error,
)
from app.services import opensearch_chunk_service
from app.services.document_process_tasks import (
    DocumentProcessCancelled,
    cancel_force_and_wait,
    check_cancelled,
    make_task_key,
    register_task,
    request_cancel,
    unregister_task,
    wait_task_finished,
)


BACKEND_DIR = Path(__file__).resolve().parents[2]
STORAGE_ROOT = BACKEND_DIR / "storage" / "knowledge_files"
SUPPORTED_EXTENSIONS = {"txt", "md", "pdf", "docx", "xlsx", "xlsm", "xls", "csv"}
settings = get_settings()

MAX_PARSE_LOG_LINES = 2000

_DOCUMENT_IN_PROGRESS_STATUSES = (
    KnowledgeDocumentStatus.PARSING.value,
    KnowledgeDocumentStatus.GRAPH_INDEXING.value,
    KnowledgeDocumentStatus.CHUNKING.value,
    KnowledgeDocumentStatus.INDEXING.value,
)

_PHASE_PERCENT_RANGES: dict[str, tuple[float, float]] = {
    "parsing": (0.0, 15.0),
    "chunking": (15.0, 25.0),
    "embedding": (25.0, 70.0),
    "indexing": (70.0, 95.0),
    "graph_indexing": (25.0, 95.0),
    "queued": (25.0, 25.0),
    "done": (100.0, 100.0),
}

MINERU_VIEW_MD_FILENAME = "mineru_markdown.md"
MINERU_VIEW_CL_FILENAME = "mineru_content_list.json"


def _persist_mineru_view_artifacts(*, parsed, file_path: Path) -> None:
    """将解析引擎 markdown / content_list 落盘，供前端「Markdown / JSON」视图读取。"""
    meta = parsed.metadata if isinstance(parsed.metadata, dict) else None
    if not meta:
        return
    backend = meta.get("parser_backend")
    if backend not in {"mineru", "opendataloader"}:
        return
    parent = file_path.parent
    md = meta.pop("_parse_markdown", None) or meta.pop("_mineru_markdown", None)
    cl = meta.pop("_parse_content_list", None) or meta.pop("_mineru_content_list", None)
    view: dict[str, bool] = {"markdown": False, "content_list": False}
    if isinstance(md, str) and md.strip():
        (parent / MINERU_VIEW_MD_FILENAME).write_text(md, encoding="utf-8")
        view["markdown"] = True
    if isinstance(cl, list) and len(cl) > 0:
        (parent / MINERU_VIEW_CL_FILENAME).write_text(json.dumps(cl, ensure_ascii=False), encoding="utf-8")
        view["content_list"] = True
    meta["parse_view"] = view
    meta["mineru_view"] = view  # 兼容旧 metadata 读取


def _pdf_parser_options_from_kb(knowledge_base: KnowledgeBase) -> tuple[str | None, bool | None]:
    cfg = knowledge_base.config if isinstance(knowledge_base.config, dict) else {}
    from app.core.opendataloader_gateway import resolve_pdf_parser, resolve_pdf_parser_hybrid

    parser = resolve_pdf_parser(cfg)
    hybrid = resolve_pdf_parser_hybrid(cfg) if parser == "opendataloader" else None
    return parser, hybrid


def _clear_document_storage_dir(storage_path: str | None) -> None:
    """删除文档目录下所有文件（含 MinerU 侧车文件），再尝试移除空目录。"""
    if not storage_path:
        return
    file_path = Path(storage_path)
    parent = file_path.parent
    if not parent.is_dir():
        if file_path.is_file():
            file_path.unlink(missing_ok=True)
        return
    for child in parent.iterdir():
        if child.is_file():
            child.unlink(missing_ok=True)
    try:
        parent.rmdir()
    except OSError:
        pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_phase_percent(
    phase: str,
    *,
    current: int | None = None,
    total: int | None = None,
) -> float:
    start, end = _PHASE_PERCENT_RANGES.get(phase, (0.0, 100.0))
    if current is not None and total is not None and total > 0:
        ratio = min(max(current / total, 0.0), 1.0)
        return round(start + (end - start) * ratio, 2)
    if phase == "parsing":
        return round(start + (end - start) * 0.3, 2)
    if phase in ("chunking", "indexing", "done"):
        return end
    return start


def _build_progress_payload(
    *,
    phase: str,
    current: int | None = None,
    total: int | None = None,
    message: str = "",
) -> dict[str, Any]:
    return {
        "type": "progress",
        "phase": phase,
        "percent": _compute_phase_percent(phase, current=current, total=total),
        "current": current,
        "total": total,
        "message": message,
    }


def _build_parse_log_payload(
    kind: Literal["parse", "reindex"],
    phase: Literal["success", "error"],
    lines: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "kind": kind,
        "phase": phase,
        "lines": lines[-MAX_PARSE_LOG_LINES:],
        "updated_at": _utc_now_iso(),
    }


def _storage_path_for(document: KnowledgeDocument) -> Path:
    extension = f".{document.file_ext}" if document.file_ext else ""
    return STORAGE_ROOT / str(document.enterprise_space_id) / str(document.knowledge_base_id) / str(document.id) / f"original{extension}"


def resolve_original_file_path(document: KnowledgeDocument) -> Path | None:
    """
    定位磁盘上的原始上传文件。
    依次尝试数据库中的 storage_path、以及按规范拼装的 STORAGE_ROOT 路径，
    用于兼容宿主机与容器内工作目录不一致时 DB 中仍为旧绝对路径的情况。
    """
    candidates: list[Path] = []
    if document.storage_path and str(document.storage_path).strip():
        candidates.append(Path(document.storage_path))
    candidates.append(_storage_path_for(document))
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            if path.is_file():
                return path
        except OSError:
            continue
    return None


def _document_file_ext(file_name: str) -> str:
    extension = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    if extension == "doc":
        raise AppError(
            status_code=400,
            code="UNSUPPORTED_FILE_TYPE",
            message="暂不支持旧版 Word（.doc），请在 Word 中另存为 .docx 后再上传。",
        )
    if extension not in SUPPORTED_EXTENSIONS:
        raise AppError(
            status_code=400,
            code="UNSUPPORTED_FILE_TYPE",
            message="仅支持 txt、md、pdf、docx、csv 与 Excel（xls / xlsx / xlsm）等常见文本类格式",
        )
    return extension


def _normalize_pagination(page: int, page_size: int) -> tuple[int, int]:
    safe_page = max(page, 1)
    safe_page_size = min(max(page_size, 1), 100)
    return safe_page, safe_page_size


def _sanitize_pg_text(value: str | None, *, max_len: int | None = None) -> str:
    """PostgreSQL TEXT / VARCHAR 不能包含 NUL（\\x00）；解析器误读二进制时也会产生此类字节。"""
    if value is None:
        return ""
    s = value.replace("\x00", "")
    if max_len is not None and len(s) > max_len:
        s = s[:max_len]
    return s


def _document_chunk_uid(document_id: int, chunk_index: int) -> str:
    return f"doc{document_id}-{chunk_index:04d}-{uuid4().hex[:12]}"


def serialize_document(document: KnowledgeDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "enterprise_space_id": document.enterprise_space_id,
        "knowledge_base_id": document.knowledge_base_id,
        "source_type": document.source_type,
        "document_name": document.document_name,
        "file_name": document.file_name,
        "file_ext": document.file_ext,
        "mime_type": document.mime_type,
        "file_size": document.file_size,
        "storage_type": document.storage_type,
        "parser_type": document.parser_type,
        "chunk_size": document.chunk_size,
        "chunk_overlap": document.chunk_overlap,
        "status": document.status,
        "chunk_count": document.chunk_count,
        "token_count": document.token_count,
        "char_count": document.char_count,
        "error_message": document.error_message,
        "metadata": document.metadata_json,
        "chunking_config": document.chunking_config_json,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


def serialize_chunk(chunk: KnowledgeChunk) -> dict[str, Any]:
    return {
        "id": chunk.id,
        "chunk_uid": chunk.chunk_uid,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "content_preview": chunk.content_preview,
        "char_count": chunk.char_count,
        "token_count": chunk.token_count,
        "start_offset": chunk.start_offset,
        "end_offset": chunk.end_offset,
        "page_no": chunk.page_no,
        "heading_path": chunk.heading_path,
        "vector_status": chunk.vector_status,
        "vector_id": chunk.vector_id,
        "metadata": chunk.metadata_json,
        "created_at": chunk.created_at,
        "updated_at": chunk.updated_at,
    }


def get_document_or_error(db: Session, *, space_id: int, kb_id: int, document_id: int) -> KnowledgeDocument:
    document = db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.enterprise_space_id == space_id,
            KnowledgeDocument.knowledge_base_id == kb_id,
        )
    ).scalar_one_or_none()
    if document is None:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    return document


def get_knowledge_chunk_serialized(db: Session, *, space_id: int, kb_id: int, chunk_id: int) -> dict[str, Any]:
    get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id, include_deleted=False)
    chunk = db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.id == chunk_id,
            KnowledgeChunk.enterprise_space_id == space_id,
            KnowledgeChunk.knowledge_base_id == kb_id,
        )
    ).scalar_one_or_none()
    if chunk is None:
        raise AppError(status_code=404, code="CHUNK_NOT_FOUND", message="切片不存在或无权访问")
    return serialize_chunk(chunk)


_DOCUMENT_LIST_SORTS = frozenset({"created_desc", "created_asc", "name_asc", "updated_desc"})


def list_documents(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    status: str | None,
    keyword: str | None,
    page: int,
    page_size: int,
    sort: str | None = None,
) -> dict[str, Any]:
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id, include_deleted=True)
    safe_page, safe_page_size = _normalize_pagination(page, page_size)

    filters = [
        KnowledgeDocument.enterprise_space_id == space_id,
        KnowledgeDocument.knowledge_base_id == kb_id,
        KnowledgeDocument.status != KnowledgeDocumentStatus.DELETED.value,
    ]
    if status:
        filters.append(KnowledgeDocument.status == status)
    if keyword:
        filters.append(
            or_(
                KnowledgeDocument.document_name.ilike(f"%{keyword}%"),
                KnowledgeDocument.file_name.ilike(f"%{keyword}%"),
            )
        )

    sort_key = (sort or "created_desc").strip().lower()
    if sort_key not in _DOCUMENT_LIST_SORTS:
        sort_key = "created_desc"
    order_columns: tuple = ()
    if sort_key == "created_desc":
        order_columns = (KnowledgeDocument.created_at.desc(), KnowledgeDocument.id.desc())
    elif sort_key == "created_asc":
        order_columns = (KnowledgeDocument.created_at.asc(), KnowledgeDocument.id.asc())
    elif sort_key == "name_asc":
        order_columns = (KnowledgeDocument.document_name.asc(), KnowledgeDocument.id.asc())
    else:
        order_columns = (KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())

    total = db.execute(select(func.count(KnowledgeDocument.id)).where(*filters)).scalar_one()
    documents = db.execute(
        select(KnowledgeDocument)
        .where(*filters)
        .order_by(*order_columns)
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
    ).scalars().all()

    if is_lightrag_kb(knowledge_base) and documents:
        from app.services.lightrag_engine import apply_lightrag_chunk_counts

        apply_lightrag_chunk_counts(knowledge_base, list(documents))

    return {
        "items": [serialize_document(document) for document in documents],
        "total": int(total),
        "page": safe_page,
        "page_size": safe_page_size,
    }


def get_document_detail(db: Session, *, space_id: int, kb_id: int, document_id: int) -> dict[str, Any]:
    document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id, include_deleted=True)
    if is_lightrag_kb(knowledge_base):
        from app.services.lightrag_engine import apply_lightrag_chunk_counts

        apply_lightrag_chunk_counts(knowledge_base, [document])
    return serialize_document(document)


def update_document_chunking_config(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    document_id: int,
    chunking_config: dict | None,
) -> dict[str, Any]:
    document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    document.chunking_config_json = chunking_config if isinstance(chunking_config, dict) else None
    db.commit()
    db.refresh(document)
    return serialize_document(document)


def _preview_excerpt_from_chunks(
    full_text: str, preview_candidates: list[ChunkCandidate], *, max_chars: int
) -> tuple[str, bool]:
    """用本批预览块在全文中的 offset 并集截取原文，再按 max_chars 截断。"""
    if not preview_candidates:
        return "", False
    starts: list[int] = []
    ends: list[int] = []
    for c in preview_candidates:
        if c.start_offset is not None:
            starts.append(int(c.start_offset))
        if c.end_offset is not None:
            ends.append(int(c.end_offset))
    if starts and ends:
        start_idx = max(0, min(starts))
        end_idx = min(len(full_text), max(ends))
        if start_idx >= end_idx:
            raw = "\n\n".join(x.content for x in preview_candidates if getattr(x, "content", ""))
        else:
            raw = full_text[start_idx:end_idx]
    else:
        raw = "\n\n".join(x.content for x in preview_candidates if getattr(x, "content", ""))
    truncated = len(raw) > max_chars
    return raw[:max_chars], truncated


def _explode_child_text_for_preview(text: str, *, max_piece: int) -> list[str]:
    """
    仅用于预览：当单条子段很长且内部几乎没有 child_delimiter 切分时，再拆成多条以便展示 C-1/C-2…
    与最终向量子块边界不必一致。
    """
    t = text.strip()
    if not t:
        return []
    if len(t) <= max_piece:
        return [t]
    parts: list[str] = []
    i = 0
    n = len(t)
    while i < n:
        j = min(n, i + max_piece)
        if j < n:
            window = t[i:j]
            cut_rel = -1
            for sep in ("\n\n", "\n", "。", "！", "？", "；", "，", "、", ";", ",", " "):
                p = window.rfind(sep)
                if p >= max(12, max_piece // 3):
                    cut_rel = p + len(sep)
                    break
            if cut_rel > 0:
                j = i + cut_rel
        piece = t[i:j].strip()
        if piece:
            parts.append(piece)
        if j <= i:
            j = i + max_piece
        i = j
    return parts if parts else [t]


def _build_parent_child_groups_from_segments(
    segments: list[ParsedSegment],
    *,
    max_entries: int,
    preview_piece_target: int = 88,
) -> list[dict[str, Any]]:
    """
    按 parent_index 将「父子分段引擎输出的子段」分组，供预览展示 C-1、C-2…

    必须用 apply_parent_child_chunking 之后、chunk_segments 之前的 ParsedSegment：
    向量切块后同一父块往往只有一条子向量块，若按 ChunkCandidate 分组则每组只会出现 C-1。
    """
    order: list[int] = []
    buckets: dict[int, list[ParsedSegment]] = {}
    for seg in segments:
        m = seg.metadata or {}
        if m.get("chunking_mode") != "parent_child":
            continue
        pid_raw = m.get("parent_index")
        if pid_raw is None:
            continue
        pid = int(pid_raw)
        if pid not in buckets:
            buckets[pid] = []
            order.append(pid)
        buckets[pid].append(seg)

    out: list[dict[str, Any]] = []
    global_idx = 0
    used = 0
    for pid in order:
        if used >= max_entries:
            break
        arr = buckets[pid]
        m0 = arr[0].metadata or {}
        pchar = m0.get("parent_char_count")
        if pchar is None:
            pchar = len(str(m0.get("parent_preview", "")))
        children: list[dict[str, Any]] = []
        for seg in arr:
            if used >= max_entries:
                break
            for piece in _explode_child_text_for_preview(seg.text, max_piece=preview_piece_target):
                if used >= max_entries:
                    break
                children.append(
                    {
                        "chunk_index": global_idx,
                        "content": piece,
                        "char_count": len(piece),
                    }
                )
                global_idx += 1
                used += 1
        if children:
            out.append(
                {
                    "parent_index": pid,
                    "parent_preview": str(m0.get("parent_preview", "")),
                    "parent_char_count": int(pchar),
                    "children": children,
                }
            )
    return out


def preview_document_chunking(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    document_id: int,
    chunking_config: dict,
    max_pages: int,
    max_chars: int,
    max_chunks: int,
) -> dict[str, Any]:
    """仅预览：临时解析 + 按配置分段 + 分块，不写入数据库/向量库。"""
    _ = max_pages  # 请求体保留该字段以兼容旧客户端
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id, include_deleted=True)
    document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    file_path = resolve_original_file_path(document)
    if not file_path:
        raise AppError(status_code=404, code="DOCUMENT_FILE_NOT_FOUND", message="原始文档文件不存在")

    file_bytes = file_path.read_bytes()
    pdf_parser, pdf_parser_hybrid = _pdf_parser_options_from_kb(knowledge_base)
    parsed = parse_document(
        document.file_name,
        file_bytes,
        log=None,
        pdf_parser=pdf_parser,
        pdf_parser_hybrid=pdf_parser_hybrid,
    )
    parsed.segments = merge_leading_preamble_segments(parsed.segments, full_text=parsed.text)
    if not parsed.text.strip():
        return {
            "document_id": document.id,
            "file_name": document.file_name,
            "mode": "empty",
            "excerpt": "",
            "chunks": [],
            "total_chunks": 0,
            "preview_chunk_count": 0,
            "excerpt_truncated": False,
            "parent_child_groups": None,
        }

    effective = {"chunking": chunking_config} if isinstance(chunking_config, dict) else (knowledge_base.config or {})
    cfg = parse_chunking_config(effective, fallback_chunk_size=document.chunk_size, fallback_overlap=document.chunk_overlap)

    if cfg.mode == "parent_child":
        base_segments = apply_parent_child_chunking(segments=parsed.segments, cfg=cfg.parent_child)
        chunk_size = cfg.parent_child.child_max_length
        chunk_overlap = cfg.parent_child.child_overlap
    else:
        base_segments = apply_general_chunking(
            segments=parsed.segments,
            delimiter=cfg.general.delimiter,
            collapse_whitespace=cfg.general.collapse_whitespace,
        )
        chunk_size = cfg.general.max_length
        chunk_overlap = cfg.general.overlap

    # 父子模式不做相邻段预算合并，否则会合并同一父块下多个子段，破坏 C-1/C-2… 粒度
    if cfg.mode != "parent_child":
        chunk_size, chunk_overlap = adapt_chunk_size_for_small_doc(base_segments, chunk_size, chunk_overlap)
        base_segments = merge_adjacent_segments_by_budget(base_segments, chunk_size)
    chunk_candidates = chunk_segments(base_segments, chunk_size, chunk_overlap)
    if not chunk_candidates:
        raise AppError(status_code=400, code="DOCUMENT_CHUNK_EMPTY", message="文档分块结果为空")

    total = len(chunk_candidates)
    preview_slice = chunk_candidates[:max_chunks]
    chunks = [c.content for c in preview_slice]
    excerpt, excerpt_truncated = _preview_excerpt_from_chunks(parsed.text, preview_slice, max_chars=max_chars)
    parent_child_groups: list[dict[str, Any]] | None = None
    if cfg.mode == "parent_child" and base_segments:
        # 子段条数上限略高于向量预览块数，便于看到同一父块下 C-1/C-2…
        seg_budget = min(500, max(max_chunks * 5, max_chunks))
        piece_target = max(48, min(120, cfg.parent_child.child_max_length // 3))
        groups = _build_parent_child_groups_from_segments(
            base_segments,
            max_entries=seg_budget,
            preview_piece_target=piece_target,
        )
        parent_child_groups = groups if groups else None
    return {
        "document_id": document.id,
        "file_name": document.file_name,
        "mode": cfg.mode,
        "excerpt": excerpt,
        "chunks": chunks,
        "total_chunks": total,
        "preview_chunk_count": len(chunks),
        "excerpt_truncated": excerpt_truncated,
        "parent_child_groups": parent_child_groups,
    }


def list_document_chunks(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    document_id: int,
    page: int,
    page_size: int,
    keyword: str | None = None,
) -> dict[str, Any]:
    document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")

    safe_page, safe_page_size = _normalize_pagination(page, page_size)
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id, include_deleted=True)
    if (
        knowledge_base.kb_type == KnowledgeBaseType.LIGHTRAG.value
        and document.status == KnowledgeDocumentStatus.GRAPH_INDEXED.value
    ):
        from app.services.lightrag_engine import list_lightrag_document_chunks

        return list_lightrag_document_chunks(
            knowledge_base,
            document,
            page=safe_page,
            page_size=safe_page_size,
            keyword=keyword,
        )

    chunk_filter = [KnowledgeChunk.document_id == document_id]
    if keyword and keyword.strip():
        chunk_filter.append(KnowledgeChunk.content.ilike(f"%{keyword.strip()}%"))
    total = db.execute(select(func.count(KnowledgeChunk.id)).where(*chunk_filter)).scalar_one()
    chunks = db.execute(
        select(KnowledgeChunk)
        .where(*chunk_filter)
        .order_by(KnowledgeChunk.chunk_index.asc())
        .offset((safe_page - 1) * safe_page_size)
        .limit(safe_page_size)
    ).scalars().all()
    return {
        "items": [serialize_chunk(chunk) for chunk in chunks],
        "total": int(total),
        "page": safe_page,
        "page_size": safe_page_size,
    }


def _mark_document_failed(
    db: Session,
    *,
    document_id: int,
    message: str,
    parse_log_payload: dict[str, Any] | None = None,
) -> None:
    failed_document = db.get(KnowledgeDocument, document_id)
    if failed_document is None:
        return
    kb = db.get(KnowledgeBase, failed_document.knowledge_base_id)
    if kb is not None and kb.kb_type == KnowledgeBaseType.LIGHTRAG.value:
        failed_document.status = KnowledgeDocumentStatus.GRAPH_FAILED.value
    else:
        failed_document.status = KnowledgeDocumentStatus.FAILED.value
    failed_document.error_message = message[:2000]
    failed_document.chunk_count = db.execute(
        select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.document_id == document_id)
    ).scalar_one()
    if parse_log_payload is not None:
        failed_document.parse_log_json = parse_log_payload
    db.commit()


def _clear_document_chunks_and_vectors(db: Session, *, knowledge_base: KnowledgeBase, document: KnowledgeDocument) -> None:
    opensearch_chunk_service.delete_by_document_id(document.id)
    chunks = db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.document_id == document.id)
        .order_by(KnowledgeChunk.chunk_index.asc())
    ).scalars().all()
    chunk_uids = [chunk.chunk_uid for chunk in chunks if chunk.chunk_uid]

    if chunk_uids and knowledge_base.vector_db_enabled:
        ensure_knowledge_base_milvus_fields(db, knowledge_base)
        result = delete_vectors(
            host=settings.milvus_host,
            port=settings.milvus_port,
            collection_name=knowledge_base.milvus_collection_name,
            chunk_uids=chunk_uids,
            username=settings.milvus_username,
            password=settings.milvus_password,
        )
        if not result.success:
            raise AppError(status_code=502, code="MILVUS_DELETE_FAILED", message=result.message)

    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
    document.chunk_count = 0


def _index_document_lightrag(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    parsed_text: str,
    parsed_metadata: dict | None,
    parser_type: str,
    char_count: int,
    emit: Callable[[str], None],
    emit_progress: Callable[..., None] | None = None,
    cancel_event: threading.Event | None = None,
    log_kind: Literal["parse", "reindex"],
    log_lines: list[dict[str, str]],
) -> dict[str, Any]:
    from app.services.lightrag_engine import delete_document as lightrag_delete_document
    from app.services.lightrag_engine import (
        describe_lightrag_models_for_log,
        ensure_lightrag_embedding_dimension,
        insert_document as lightrag_insert_document,
        lightrag_document_chunk_count,
    )

    def _progress(phase: str, *, current: int | None = None, total: int | None = None, message: str = "") -> None:
        check_cancelled(cancel_event)
        if emit_progress:
            emit_progress(phase=phase, current=current, total=total, message=message)
        if message:
            if len(log_lines) < MAX_PARSE_LOG_LINES:
                log_lines.append({"t": _utc_now_iso(), "text": message})
            emit(message)

    ensure_lightrag_embedding_dimension(db, knowledge_base)
    document.parser_type = parser_type
    document.char_count = char_count
    document.metadata_json = parsed_metadata
    document.chunk_count = 0
    document.status = KnowledgeDocumentStatus.GRAPH_INDEXING.value
    document.error_message = None
    db.commit()
    db.refresh(document)
    _progress("graph_indexing", message="图知识库：跳过经典分块，进入 LightRAG 图谱入库（graph_indexing）…")
    embed_log, llm_log = describe_lightrag_models_for_log(db, knowledge_base)
    emit(embed_log)
    emit(llm_log)

    if log_kind == "reindex":
        try:
            emit("重建索引：先删除 LightRAG 中旧文档图谱…")
            lightrag_delete_document(db, knowledge_base=knowledge_base, document=document)
        except AppError as exc:
            if exc.code not in ("LIGHTRAG_QUERY_FAILED",):
                emit(f"删除旧图谱警告：{exc.message}")

    try:
        emit("LightRAG 实体抽取与图谱入库中，约需数分钟，请耐心等待…")
        emit(f"调用 LightRAG ainsert，文本长度 {len(parsed_text)} 字符…")

        def _lightrag_progress(phase: str, current: int | None, total: int | None, message: str) -> None:
            if phase == "queued":
                _progress("queued", message=message)
            else:
                _progress("graph_indexing", current=current, total=total, message=message)

        lightrag_insert_document(
            db,
            knowledge_base=knowledge_base,
            document=document,
            text=parsed_text,
            on_progress=emit,
            on_structured_progress=_lightrag_progress,
            cancel_event=cancel_event,
        )
    except DocumentProcessCancelled:
        raise
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            status_code=502,
            code="LIGHTRAG_INSERT_FAILED",
            message=f"LightRAG 入库失败：{exc}",
        ) from exc

    check_cancelled(cancel_event)
    document.chunk_count = lightrag_document_chunk_count(knowledge_base, document)
    document.status = KnowledgeDocumentStatus.GRAPH_INDEXED.value
    document.parse_log_json = _build_parse_log_payload(log_kind, "success", log_lines)
    db.commit()
    db.refresh(document)
    _progress(
        "done",
        message=f"完成：状态=图谱已就绪（graph_indexed），chunk_count={document.chunk_count}",
    )
    return serialize_document(document)


def _index_document(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    embedding_model_id: int | None = None,
    emit: Callable[[str], None] | None = None,
    emit_progress: Callable[..., None] | None = None,
    cancel_event: threading.Event | None = None,
    log_kind: Literal["parse", "reindex"] = "parse",
) -> dict[str, Any]:
    log_lines: list[dict[str, str]] = []
    document.parse_log_json = None

    def _progress(phase: str, *, current: int | None = None, total: int | None = None, message: str = "") -> None:
        check_cancelled(cancel_event)
        if emit_progress:
            emit_progress(phase=phase, current=current, total=total, message=message)
        if message:
            _emit(message)

    def _emit(msg: str) -> None:
        if len(log_lines) < MAX_PARSE_LOG_LINES:
            log_lines.append({"t": _utc_now_iso(), "text": msg})
        if emit:
            emit(msg)

    try:
        check_cancelled(cancel_event)
        _emit(
            f"开始索引：文档 id={document.id}「{document.file_name}」"
            f"，chunk_size={document.chunk_size} overlap={document.chunk_overlap}"
        )
        if knowledge_base.kb_type == KnowledgeBaseType.LIGHTRAG.value:
            from app.services.lightrag_engine import describe_lightrag_models_for_log

            embed_log, llm_log = describe_lightrag_models_for_log(db, knowledge_base)
            _emit(embed_log)
            _emit(llm_log)
        elif knowledge_base.vector_db_enabled:
            embedding_model = get_embedding_model_for_knowledge_base(
                db,
                knowledge_base=knowledge_base,
                override_model_id=embedding_model_id,
            )
            _emit(format_ai_model_for_log(embedding_model, role="Embedding 模型"))
        file_path = resolve_original_file_path(document)
        if not file_path:
            raise AppError(status_code=404, code="DOCUMENT_FILE_NOT_FOUND", message="原始文档文件不存在")

        document.status = KnowledgeDocumentStatus.PARSING.value
        document.error_message = None
        db.commit()
        db.refresh(document)
        _progress("parsing", message="状态：解析中（PARSING）")
        _emit(f"状态：解析中（PARSING），读取文件 {file_path}")
        file_bytes = file_path.read_bytes()
        check_cancelled(cancel_event)
        _emit(f"已读入 {len(file_bytes)} 字节，调用解析器…")
        pdf_parser, pdf_parser_hybrid = _pdf_parser_options_from_kb(knowledge_base)
        try:
            parsed = parse_document(
                document.file_name,
                file_bytes,
                log=_emit,
                pdf_parser=pdf_parser,
                pdf_parser_hybrid=pdf_parser_hybrid,
            )
            _persist_mineru_view_artifacts(parsed=parsed, file_path=file_path)
        except UnsupportedDocumentError as exc:
            _emit(f"解析失败（不支持或依赖缺失）：{exc.message}")
            raise AppError(status_code=400, code="DOCUMENT_PARSE_FAILED", message=exc.message) from exc
        if not parsed.text.strip():
            _emit("解析结果文本为空")
            raise AppError(status_code=400, code="DOCUMENT_PARSE_EMPTY", message="文档解析后内容为空")
        try:
            validate_parsed_document_for_indexing(parsed)
        except UnsupportedDocumentError as exc:
            _emit(f"解析质量检查未通过：{exc.message}")
            raise AppError(status_code=400, code="DOCUMENT_PARSE_LOW_QUALITY", message=exc.message) from exc

        n_seg_pre = len(parsed.segments)
        parsed.segments = merge_leading_preamble_segments(parsed.segments, full_text=parsed.text)
        if len(parsed.segments) != n_seg_pre:
            _emit(f"封面/文前短段已合并为 1 条分段：{n_seg_pre} → {len(parsed.segments)}")

        if parsed.parser_type == "pdf":
            _emit("PDF 解析完成，准备入库…")
        else:
            _emit(f"文档解析完成（{parsed.parser_type}），准备入库…")
        _progress("parsing", current=1, total=1, message="文档解析完成")

        if knowledge_base.kb_type == KnowledgeBaseType.LIGHTRAG.value:
            return _index_document_lightrag(
                db,
                knowledge_base=knowledge_base,
                document=document,
                parsed_text=parsed.text,
                parsed_metadata=parsed.metadata,
                parser_type=parsed.parser_type,
                char_count=parsed.char_count,
                emit=_emit,
                emit_progress=emit_progress,
                cancel_event=cancel_event,
                log_kind=log_kind,
                log_lines=log_lines,
            )

        document.status = KnowledgeDocumentStatus.CHUNKING.value
        document.parser_type = parsed.parser_type
        document.char_count = parsed.char_count
        document.metadata_json = parsed.metadata
        meta_preview = json.dumps(parsed.metadata, ensure_ascii=False)
        if len(meta_preview) > 800:
            meta_preview = meta_preview[:800] + "…"
        _emit(f"解析完成：parser_type={parsed.parser_type}，字符数={parsed.char_count}，原始分段数={len(parsed.segments)}")
        _emit(f"metadata: {meta_preview}")

        _progress("chunking", message="状态：分块中（CHUNKING）")
        _emit("状态：分块中（CHUNKING）…")
        effective_config = knowledge_base.config
        if document.chunking_config_json and isinstance(document.chunking_config_json, dict):
            effective_config = {"chunking": document.chunking_config_json}
        chunking_cfg = parse_chunking_config(
            effective_config,
            fallback_chunk_size=document.chunk_size,
            fallback_overlap=document.chunk_overlap,
        )
        if chunking_cfg.mode == "parent_child":
            _emit(
                "分段模式：父子分段（子块用于索引），"
                f"parent_mode={chunking_cfg.parent_child.parent_mode} "
                f"child_delim={chunking_cfg.parent_child.child_delimiter!r} "
                f"child_max={chunking_cfg.parent_child.child_max_length} "
                f"child_overlap={chunking_cfg.parent_child.child_overlap}"
            )
            base_segments = apply_parent_child_chunking(segments=parsed.segments, cfg=chunking_cfg.parent_child)
            chunk_size = chunking_cfg.parent_child.child_max_length
            chunk_overlap = chunking_cfg.parent_child.child_overlap
        else:
            _emit(
                "分段模式：通用分段，"
                f"delim={chunking_cfg.general.delimiter!r} "
                f"max={chunking_cfg.general.max_length} "
                f"overlap={chunking_cfg.general.overlap}"
            )
            base_segments = apply_general_chunking(
                segments=parsed.segments,
                delimiter=chunking_cfg.general.delimiter,
                collapse_whitespace=chunking_cfg.general.collapse_whitespace,
            )
            chunk_size = chunking_cfg.general.max_length
            chunk_overlap = chunking_cfg.general.overlap

        n_seg_before = len(base_segments)
        if chunking_cfg.mode != "parent_child":
            adapted_size, adapted_overlap = adapt_chunk_size_for_small_doc(base_segments, chunk_size, chunk_overlap)
            if adapted_size != chunk_size:
                _emit(f"小文档自适应：chunk_size {chunk_size}→{adapted_size}, overlap {chunk_overlap}→{adapted_overlap}")
                chunk_size, chunk_overlap = adapted_size, adapted_overlap
            base_segments = merge_adjacent_segments_by_budget(base_segments, chunk_size)
            _emit(f"相邻段合并（字符预算={chunk_size}）：分段 {n_seg_before} → {len(base_segments)}，再按长度切块")
        else:
            _emit("父子模式：跳过相邻段预算合并，保留子段边界（与父块内 C-1、C-2… 预览一致）")
        chunk_candidates = chunk_segments(base_segments, chunk_size, chunk_overlap)
        if not chunk_candidates:
            _emit("分块结果为空")
            raise AppError(status_code=400, code="DOCUMENT_CHUNK_EMPTY", message="文档分块结果为空")
        max_indexable_chunks = 2500
        if len(chunk_candidates) > max_indexable_chunks:
            backend = str((parsed.metadata or {}).get("parser_backend") or "")
            _emit(
                f"分块数量 {len(chunk_candidates)} 超过上限 {max_indexable_chunks}（parser_backend={backend}）"
            )
            raise AppError(
                status_code=400,
                code="DOCUMENT_TOO_MANY_CHUNKS",
                message=(
                    f"分块数量 {len(chunk_candidates)} 异常偏高（政策类 PDF 通常在数百块以内），"
                    "可能因未正确提取正文（扫描件、复杂版式或兜底解析产生乱码）。"
                    "请在 .env 设置 MINERU_ENABLED=true 并启动 mineru 服务后重新解析。"
                ),
            )
        _emit(f"分块完成：候选块数量 {len(chunk_candidates)}")
        _progress("chunking", current=1, total=1, message="分块完成")

        existing_chunk_count = db.execute(
            select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.document_id == document.id)
        ).scalar_one()
        if existing_chunk_count:
            _emit(f"写入前清理残留分块 {int(existing_chunk_count)} 条…")
            _clear_document_chunks_and_vectors(db, knowledge_base=knowledge_base, document=document)
            document.chunk_count = 0
            db.flush()

        chunk_records: list[KnowledgeChunk] = []
        vector_status = (
            KnowledgeChunkVectorStatus.PENDING.value
            if knowledge_base.vector_db_enabled
            else KnowledgeChunkVectorStatus.INDEXED.value
        )
        for candidate in chunk_candidates:
            raw_content = candidate.content
            content = _sanitize_pg_text(raw_content)
            if not content.strip():
                content = " "
            preview = _sanitize_pg_text(candidate.content_preview, max_len=300)
            if not preview:
                preview = content[:300] if len(content) > 300 else content
            elif len(preview) > 300:
                preview = preview[:300]
            heading_path = _sanitize_pg_text(candidate.heading_path, max_len=500) or None
            if heading_path == "":
                heading_path = None
            keyword = content
            chunk = KnowledgeChunk(
                enterprise_space_id=document.enterprise_space_id,
                knowledge_base_id=document.knowledge_base_id,
                document_id=document.id,
                chunk_uid=_document_chunk_uid(document.id, candidate.chunk_index),
                chunk_index=candidate.chunk_index,
                content=content,
                content_preview=preview if preview else None,
                char_count=len(content),
                token_count=None,
                start_offset=candidate.start_offset,
                end_offset=candidate.end_offset,
                page_no=candidate.page_no,
                heading_path=heading_path,
                keyword_text=keyword,
                vector_status=vector_status,
                vector_id=None,
                metadata_json=candidate.metadata,
            )
            db.add(chunk)
            chunk_records.append(chunk)

        document.status = KnowledgeDocumentStatus.INDEXING.value
        document.chunk_count = len(chunk_records)
        db.flush()
        _emit(f"已写入数据库分块记录 {len(chunk_records)} 条（flush）")

        if knowledge_base.vector_db_enabled:
            _progress("embedding", current=0, total=len(chunk_records), message="准备生成向量")
            _emit("知识库已启用向量库：准备 embedding 与 Milvus 写入…")
            ensure_knowledge_base_milvus_fields(db, knowledge_base)
            embedding_model = get_embedding_model_for_knowledge_base(
                db,
                knowledge_base=knowledge_base,
                override_model_id=embedding_model_id,
            )
            _emit(format_ai_model_for_log(embedding_model, role="Embedding 模型"))
            total_embed = len(chunk_records)
            _emit(f"正在生成向量，文本段数 {total_embed}（可能较慢）…")

            def _embedding_progress(done: int, total: int) -> None:
                check_cancelled(cancel_event)
                _progress("embedding", current=done, total=total, message=f"向量生成进度 {done}/{total}")
                if done <= 8 or done == total or done % 500 == 0:
                    _emit(f"向量生成进度 {done}/{total}…")

            vectors = generate_embeddings(
                embedding_model,
                [chunk.content for chunk in chunk_records],
                on_progress=_embedding_progress,
            )
            vector_dimension = len(vectors[0]) if vectors else 0
            if vector_dimension <= 0:
                raise AppError(status_code=502, code="EMBEDDING_RESPONSE_INVALID", message="未返回有效向量")
            _emit(f"向量生成完成，维度={vector_dimension}")
            if knowledge_base.milvus_dimension != vector_dimension:
                indexed_document_count = db.execute(
                    select(func.count(KnowledgeDocument.id)).where(
                        KnowledgeDocument.knowledge_base_id == knowledge_base.id,
                        KnowledgeDocument.id != document.id,
                        KnowledgeDocument.status == KnowledgeDocumentStatus.INDEXED.value,
                    )
                ).scalar_one()
                if indexed_document_count:
                    raise AppError(
                        status_code=400,
                        code="MILVUS_DIMENSION_MISMATCH",
                        message=f"Milvus 配置维度为 {knowledge_base.milvus_dimension}，但 embedding 结果维度为 {vector_dimension}",
                    )
                _emit("当前知识库首次写入向量，将按新维度调整 Milvus 集合…")
                knowledge_base.milvus_dimension = vector_dimension
                reset_result = drop_collection_if_exists(
                    host=settings.milvus_host,
                    port=settings.milvus_port,
                    collection_name=knowledge_base.milvus_collection_name,
                    username=settings.milvus_username,
                    password=settings.milvus_password,
                )
                if not reset_result.success:
                    raise AppError(status_code=502, code="MILVUS_COLLECTION_FAILED", message=reset_result.message)
                db.flush()

            create_result = create_collection_if_not_exists(
                host=settings.milvus_host,
                port=settings.milvus_port,
                collection_name=knowledge_base.milvus_collection_name,
                dimension=knowledge_base.milvus_dimension,
                metric_type=knowledge_base.milvus_metric_type,
                username=settings.milvus_username,
                password=settings.milvus_password,
            )
            if not create_result.success:
                raise AppError(status_code=502, code="MILVUS_COLLECTION_FAILED", message=create_result.message)
            _emit(f"Milvus 集合就绪：{knowledge_base.milvus_collection_name}")

            metadata = [
                {
                    "chunk_uid": chunk.chunk_uid,
                    "enterprise_space_id": chunk.enterprise_space_id,
                    "knowledge_base_id": chunk.knowledge_base_id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                    "page_no": chunk.page_no,
                    "heading_path": chunk.heading_path,
                }
                for chunk in chunk_records
            ]
            _emit(f"正在写入 Milvus：{len(vectors)} 条向量 @ {settings.milvus_host}:{settings.milvus_port}…")
            _progress("indexing", current=0, total=len(vectors), message="正在写入 Milvus")
            insert_result = insert_vectors(
                host=settings.milvus_host,
                port=settings.milvus_port,
                collection_name=knowledge_base.milvus_collection_name,
                vectors=vectors,
                metadata=metadata,
                username=settings.milvus_username,
                password=settings.milvus_password,
            )
            if not insert_result.success:
                raise AppError(status_code=502, code="MILVUS_INSERT_FAILED", message=insert_result.message)
            _emit("Milvus 插入成功")
            _progress("indexing", current=len(vectors), total=len(vectors), message="Milvus 写入完成")

            for chunk in chunk_records:
                chunk.vector_status = KnowledgeChunkVectorStatus.INDEXED.value
                chunk.vector_id = chunk.chunk_uid
        else:
            _emit("知识库未启用向量库：跳过 embedding 与 Milvus，分块仅落库")

        document.status = KnowledgeDocumentStatus.INDEXED.value
        document.error_message = None
        _emit(f"完成：状态=已索引（INDEXED），chunk_count={document.chunk_count}")
        _progress("done", message="索引完成")
        document.parse_log_json = _build_parse_log_payload(log_kind, "success", log_lines)
        db.commit()
        db.refresh(document)
        opensearch_chunk_service.sync_document_after_index(
            db, document_id=document.id, document_name=document.document_name
        )
        return serialize_document(document)
    except DocumentProcessCancelled:
        raise
    except AppError as exc:
        db.rollback()
        _emit(f"业务错误：{exc.message}")
        _mark_document_failed(
            db,
            document_id=document.id,
            message=exc.message,
            parse_log_payload=_build_parse_log_payload(log_kind, "error", log_lines),
        )
        raise
    except Exception as exc:
        db.rollback()
        _emit(f"未预期异常：{exc!r}")
        _mark_document_failed(
            db,
            document_id=document.id,
            message=str(exc),
            parse_log_payload=_build_parse_log_payload(log_kind, "error", log_lines),
        )
        raise AppError(status_code=500, code="DOCUMENT_PROCESS_FAILED", message="文档处理失败") from exc


def upload_document(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    file_name: str,
    file_bytes: bytes,
    mime_type: str | None,
    chunk_size: int | None,
    chunk_overlap: int | None,
) -> dict[str, Any]:
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
    extension = _document_file_ext(file_name)
    if not file_bytes:
        raise AppError(status_code=400, code="EMPTY_FILE", message="上传文件不能为空")

    resolved_chunk_size = chunk_size or knowledge_base.default_chunk_size
    resolved_chunk_overlap = chunk_overlap if chunk_overlap is not None else knowledge_base.default_chunk_overlap
    if resolved_chunk_overlap >= resolved_chunk_size:
        raise AppError(status_code=400, code="INVALID_CHUNK_CONFIG", message="chunk_overlap 必须小于 chunk_size")

    content_sha256 = hashlib.sha256(file_bytes).hexdigest()
    duplicate = db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.knowledge_base_id == kb_id,
            KnowledgeDocument.content_sha256 == content_sha256,
        )
    ).scalar_one_or_none()
    if duplicate is not None and duplicate.status != KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=409, code="DOCUMENT_ALREADY_EXISTS", message="同一知识库内已存在相同内容的文档")

    if duplicate is not None:
        document = duplicate
        document.enterprise_space_id = space_id
        document.knowledge_base_id = kb_id
        document.source_type = "upload"
        document.document_name = Path(file_name).stem
        document.file_name = file_name
        document.file_ext = extension
        document.mime_type = mime_type
        document.file_size = len(file_bytes)
        document.storage_type = "local"
        document.storage_path = ""
        document.content_sha256 = content_sha256
        document.parser_type = extension
        document.chunk_size = resolved_chunk_size
        document.chunk_overlap = resolved_chunk_overlap
        document.status = KnowledgeDocumentStatus.UPLOADED.value
        document.chunk_count = 0
        document.token_count = None
        document.char_count = None
        document.error_message = None
        document.metadata_json = None
        document.parse_log_json = None
        opensearch_chunk_service.delete_by_document_id(document.id)
        db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document.id))
    else:
        document = KnowledgeDocument(
            enterprise_space_id=space_id,
            knowledge_base_id=kb_id,
            source_type="upload",
            document_name=Path(file_name).stem,
            file_name=file_name,
            file_ext=extension,
            mime_type=mime_type,
            file_size=len(file_bytes),
            storage_type="local",
            storage_path="",
            content_sha256=content_sha256,
            parser_type=extension,
            chunk_size=resolved_chunk_size,
            chunk_overlap=resolved_chunk_overlap,
            status=KnowledgeDocumentStatus.UPLOADED.value,
            chunk_count=0,
            metadata_json=None,
        )
        db.add(document)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(status_code=409, code="DOCUMENT_ALREADY_EXISTS", message="同一知识库内已存在相同内容的文档") from exc

    file_path = _storage_path_for(document)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(file_bytes)
    document.storage_path = str(file_path)
    db.commit()
    db.refresh(document)

    return serialize_document(document)


def process_document(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    document_id: int,
    embedding_model_id: int | None,
    emit: Callable[[str], None] | None = None,
    emit_progress: Callable[..., None] | None = None,
    cancel_event: threading.Event | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """对已上传（或解析失败）的文档执行解析、分块与索引。"""
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
    document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    if not force and document.status in (
        KnowledgeDocumentStatus.PARSING.value,
        KnowledgeDocumentStatus.GRAPH_INDEXING.value,
    ):
        raise AppError(
            status_code=409,
            code="DOCUMENT_PARSE_IN_PROGRESS",
            message="文档正在解析或图谱入库中，请勿重复提交",
        )
    if force and document.status in _DOCUMENT_IN_PROGRESS_STATUSES:
        if emit:
            emit("强制重跑：已重置进行中的任务状态")
        document.status = KnowledgeDocumentStatus.UPLOADED.value
        document.error_message = None
        db.commit()
        db.refresh(document)
    _STUCK_STATUSES = (
        KnowledgeDocumentStatus.CHUNKING.value,
        KnowledgeDocumentStatus.INDEXING.value,
    )
    if document.status not in (
        KnowledgeDocumentStatus.UPLOADED.value,
        KnowledgeDocumentStatus.FAILED.value,
        KnowledgeDocumentStatus.GRAPH_FAILED.value,
        *_STUCK_STATUSES,
    ):
        raise AppError(
            status_code=400,
            code="DOCUMENT_NOT_PARSEABLE",
            message="仅「待解析」「失败」或中断后的解析中文档可开始解析；已完成请使用「重建索引」",
        )
    if document.status in _STUCK_STATUSES or document.status in (
        KnowledgeDocumentStatus.FAILED.value,
        KnowledgeDocumentStatus.GRAPH_FAILED.value,
    ):
        document.status = KnowledgeDocumentStatus.UPLOADED.value
        document.error_message = None

    # 清理残留分块/向量，避免重复解析时违反 uq_chunk_document_index
    _clear_document_chunks_and_vectors(db, knowledge_base=knowledge_base, document=document)
    document.chunk_count = 0
    db.commit()
    db.refresh(document)

    return _index_document(
        db,
        knowledge_base=knowledge_base,
        document=document,
        embedding_model_id=embedding_model_id,
        emit=emit,
        emit_progress=emit_progress,
        cancel_event=cancel_event,
        log_kind="parse",
    )


def reindex_document(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    document_id: int,
    embedding_model_id: int | None,
    emit: Callable[[str], None] | None = None,
    emit_progress: Callable[..., None] | None = None,
    cancel_event: threading.Event | None = None,
    force: bool = False,
) -> dict[str, Any]:
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
    document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    allowed_statuses = {
        KnowledgeDocumentStatus.INDEXED.value,
        KnowledgeDocumentStatus.GRAPH_INDEXED.value,
        KnowledgeDocumentStatus.GRAPH_FAILED.value,
    }
    if knowledge_base.kb_type == KnowledgeBaseType.LIGHTRAG.value:
        allowed_statuses.add(KnowledgeDocumentStatus.UPLOADED.value)
    if document.status in _DOCUMENT_IN_PROGRESS_STATUSES:
        if not force:
            raise AppError(
                status_code=409,
                code="DOCUMENT_REINDEX_IN_PROGRESS",
                message="文档正在处理中，请勿重复提交",
            )
        if emit:
            emit("强制重跑：已重置进行中的任务状态")
    elif document.status not in allowed_statuses:
        raise AppError(
            status_code=400,
            code="REINDEX_REQUIRES_INDEXED",
            message="仅已完成索引或图谱就绪的文档可重建索引，请先使用「开始解析」",
        )

    _clear_document_chunks_and_vectors(db, knowledge_base=knowledge_base, document=document)
    if knowledge_base.kb_type == KnowledgeBaseType.LIGHTRAG.value:
        document.status = KnowledgeDocumentStatus.GRAPH_INDEXING.value
    else:
        document.status = KnowledgeDocumentStatus.UPLOADED.value
    document.error_message = None
    document.chunk_count = 0
    db.commit()
    db.refresh(document)
    return _index_document(
        db,
        knowledge_base=knowledge_base,
        document=document,
        embedding_model_id=embedding_model_id,
        emit=emit,
        emit_progress=emit_progress,
        cancel_event=cancel_event,
        log_kind="reindex",
    )


def _reset_document_after_cancel(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    document: KnowledgeDocument,
    log_kind: Literal["parse", "reindex"] = "parse",
    log_lines: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """取消后清理部分写入并将文档重置为待解析。"""
    from app.services.lightrag_engine import delete_document as lightrag_delete_document

    lines = log_lines or [{"t": _utc_now_iso(), "text": "用户已取消解析"}]
    _clear_document_chunks_and_vectors(db, knowledge_base=knowledge_base, document=document)
    if knowledge_base.kb_type == KnowledgeBaseType.LIGHTRAG.value:
        try:
            lightrag_delete_document(db, knowledge_base=knowledge_base, document=document)
        except AppError:
            pass
    document.status = KnowledgeDocumentStatus.UPLOADED.value
    document.error_message = "用户已取消解析"
    document.chunk_count = 0
    document.parse_log_json = _build_parse_log_payload(log_kind, "error", lines)
    db.commit()
    db.refresh(document)
    return serialize_document(document)


def cancel_document_process(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    document_id: int,
) -> dict[str, Any]:
    """请求取消进行中的解析/重建任务；若无活跃 worker 但 DB 卡在进行中则直接重置。"""
    key = make_task_key(space_id, kb_id, document_id)
    if request_cancel(key):
        wait_task_finished(key, timeout_sec=10.0)
        document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
        if document.status in _DOCUMENT_IN_PROGRESS_STATUSES:
            knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
            return _reset_document_after_cancel(db, knowledge_base=knowledge_base, document=document)
        return serialize_document(document)

    document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    if document.status in _DOCUMENT_IN_PROGRESS_STATUSES:
        knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
        return _reset_document_after_cancel(db, knowledge_base=knowledge_base, document=document)
    raise AppError(status_code=404, code="NO_ACTIVE_TASK", message="没有进行中的解析任务")


def get_document_parse_log(
    db: Session,
    *,
    space_id: int,
    kb_id: int,
    document_id: int,
) -> dict[str, Any]:
    document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    raw = document.parse_log_json
    if not raw or not isinstance(raw, dict):
        return {
            "kind": None,
            "phase": None,
            "lines": [],
            "updated_at": None,
        }
    lines = raw.get("lines")
    if not isinstance(lines, list):
        lines = []
    normalized: list[dict[str, str]] = []
    for item in lines:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "t": str(item.get("t", "")),
                "text": str(item.get("text", "")),
            }
        )
    return {
        "kind": raw.get("kind") if isinstance(raw.get("kind"), str) else None,
        "phase": raw.get("phase") if isinstance(raw.get("phase"), str) else None,
        "lines": normalized,
        "updated_at": raw.get("updated_at") if isinstance(raw.get("updated_at"), str) else None,
    }


def iter_document_process_sse_events(
    *,
    space_id: int,
    kb_id: int,
    document_id: int,
    embedding_model_id: int | None,
    mode: Literal["parse", "reindex"],
    force: bool = False,
    stop_event: threading.Event | None = None,
) -> Iterator[str]:
    """在独立线程与独立 Session 中执行解析/重建，通过 SSE 文本块输出日志与结果。"""
    q: queue.Queue[tuple[str, Any]] = queue.Queue()
    key = make_task_key(space_id, kb_id, document_id)
    if force:
        cancel_force_and_wait(key)

    cancel_event = threading.Event()

    def emit(msg: str) -> None:
        q.put(("log", msg))

    def emit_progress(*, phase: str, current: int | None = None, total: int | None = None, message: str = "") -> None:
        payload = _build_progress_payload(phase=phase, current=current, total=total, message=message)
        q.put(("progress", payload))

    def worker() -> None:
        with SessionLocal() as db:
            try:
                if mode == "parse":
                    result = process_document(
                        db,
                        space_id=space_id,
                        kb_id=kb_id,
                        document_id=document_id,
                        embedding_model_id=embedding_model_id,
                        emit=emit,
                        emit_progress=emit_progress,
                        cancel_event=cancel_event,
                        force=force,
                    )
                else:
                    result = reindex_document(
                        db,
                        space_id=space_id,
                        kb_id=kb_id,
                        document_id=document_id,
                        embedding_model_id=embedding_model_id,
                        emit=emit,
                        emit_progress=emit_progress,
                        cancel_event=cancel_event,
                        force=force,
                    )
                q.put(("done", result))
            except DocumentProcessCancelled:
                knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id)
                document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
                result = _reset_document_after_cancel(
                    db,
                    knowledge_base=knowledge_base,
                    document=document,
                    log_kind=mode,
                )
                q.put(("cancelled", result))
            except AppError as exc:
                q.put(("app_error", exc))
            except Exception as exc:
                q.put(("fatal", exc))
            finally:
                unregister_task(key)

    thread = threading.Thread(target=worker, daemon=True)
    register_task(key, thread=thread, cancel_event=cancel_event)
    thread.start()

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                request_cancel(key)
                break
            try:
                kind, payload = q.get(timeout=2.0)
            except queue.Empty:
                continue
            if kind == "log":
                yield f"data: {json.dumps({'type': 'log', 'message': payload}, ensure_ascii=False)}\n\n"
            elif kind == "progress":
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            elif kind == "done":
                body = jsonable_encoder({"type": "done", "document": payload})
                yield f"data: {json.dumps(body, ensure_ascii=False)}\n\n"
                break
            elif kind == "cancelled":
                body = jsonable_encoder({"type": "cancelled", "document": payload})
                yield f"data: {json.dumps(body, ensure_ascii=False)}\n\n"
                break
            elif kind == "app_error":
                exc = payload
                yield f"data: {json.dumps({'type': 'error', 'code': exc.code, 'message': exc.message}, ensure_ascii=False)}\n\n"
                break
            elif kind == "fatal":
                yield f"data: {json.dumps({'type': 'error', 'code': 'INTERNAL', 'message': str(payload)}, ensure_ascii=False)}\n\n"
                break
    finally:
        if stop_event is not None and stop_event.is_set():
            request_cancel(key)
        thread.join(timeout=5)


def delete_document_asset(db: Session, *, space_id: int, kb_id: int, document_id: int) -> None:
    knowledge_base = get_knowledge_base_or_error(db, space_id=space_id, kb_id=kb_id, include_deleted=True)
    document = get_document_or_error(db, space_id=space_id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        return

    _clear_document_chunks_and_vectors(db, knowledge_base=knowledge_base, document=document)

    if knowledge_base.kb_type == KnowledgeBaseType.LIGHTRAG.value:
        from app.services.lightrag_engine import delete_document as lightrag_delete_document

        try:
            lightrag_delete_document(db, knowledge_base=knowledge_base, document=document)
        except AppError as exc:
            if exc.code not in ("LIGHTRAG_QUERY_FAILED",):
                raise

    _clear_document_storage_dir(document.storage_path)

    document.status = KnowledgeDocumentStatus.DELETED.value
    document.error_message = None
    document.chunk_count = 0
    db.commit()
