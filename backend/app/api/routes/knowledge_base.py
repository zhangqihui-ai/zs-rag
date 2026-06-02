from __future__ import annotations

import asyncio
import logging
import mimetypes
import shutil
import threading
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enterprise_space_context import CurrentSpace, CurrentUser, RequireMembership
from app.core.errors import AppError
from app.core.knowledge_retrieval_defaults import apply_retrieval_defaults_to_payload
from app.core.neo4j_client import test_neo4j_connection
from app.db.session import SessionLocal, get_db
from app.core.milvus_client import drop_collection_if_exists
from app.models.knowledge_base import KnowledgeBase, KnowledgeChunk, KnowledgeDocument, KnowledgeDocumentStatus, Neo4jConnection
from app.schemas.knowledge_base import (
    ConnectionTestResponse,
    KnowledgeBaseCreate,
    KnowledgeBasePurgeRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseStatsResponse,
    KnowledgeBaseUpdate,
    Neo4jConnectionCreate,
    Neo4jConnectionResponse,
    Neo4jConnectionUpdate,
)
from app.schemas.knowledge_document import (
    ChunkSourceContextResponse,
    KnowledgeChunkEnrichmentRegenerateResponse,
    KnowledgeChunkEnrichmentUpdate,
    KnowledgeChunkListResponse,
    KnowledgeChunkResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentParseLogResponse,
    KnowledgeDocumentChunkingConfigUpdate,
    KnowledgeDocumentChunkingPreviewRequest,
    KnowledgeDocumentChunkingPreviewResponse,
    KnowledgeDocumentResponse,
)
from app.schemas.kb_process_log import (
    KbProcessLogBatchItemsResponse,
    KbProcessLogEventListResponse,
    KbProcessLogSummaryResponse,
    StartProcessBatchRequest,
    UploadBatchAuditRequest,
)
from app.schemas.graph_search import GraphSearchRequest, GraphSearchResponse
from app.schemas.retrieval import (
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    MultiKnowledgeSearchRequest,
    MultiKnowledgeSearchResponse,
)
from app.core.kb_type import ensure_lightrag_kb
from app.services.lightrag_engine import query_graph_kb
from app.services import kb_process_audit_service
from app.services.knowledge_base_service import (
    build_deleted_knowledge_base_name,
    build_collection_name,
    ensure_knowledge_base_name_unique,
    get_knowledge_base_or_error,
    get_knowledge_base_stats,
    get_neo4j_connection_or_error,
    resolve_knowledge_base_milvus_dimension,
)
from app.services.knowledge_document_service import (
    DOCX_VIEW_CL_FILENAME,
    DOCX_VIEW_MD_FILENAME,
    MINERU_VIEW_CL_FILENAME,
    MINERU_VIEW_MD_FILENAME,
    cancel_document_process,
    delete_document_asset,
    get_document_detail,
    get_document_or_error,
    get_document_parse_log,
    get_chunk_source_context_serialized,
    get_knowledge_chunk_serialized,
    iter_document_process_sse_events,
    list_document_chunks,
    list_documents,
    preview_document_chunking,
    process_document,
    reindex_document,
    resolve_original_file_path,
    update_document_chunking_config,
    upload_document,
)
from app.services import opensearch_chunk_service
from app.services.chunk_edit_service import regenerate_chunk_enrichment, update_chunk_enrichment
from app.services.retrieval_service import search_knowledge_base, search_knowledge_bases_multi

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-base-management"])


def _take_next_chunk(sync_iter: Iterator[str]) -> str | None:
    try:
        return next(sync_iter)
    except StopIteration:
        return None


async def _stream_document_process_sse(
    request: Request,
    *,
    space_id: int,
    kb_id: int,
    document_id: int,
    embedding_model_id: int | None,
    mode: str,
    force: bool,
    user_id: int | None = None,
    batch_uid: str | None = None,
) -> AsyncIterator[str]:
    """异步包装 SSE：客户端断开或热重载时尽快结束长连接。"""
    stop_event = threading.Event()
    sync_iter = iter_document_process_sse_events(
        space_id=space_id,
        kb_id=kb_id,
        document_id=document_id,
        embedding_model_id=embedding_model_id,
        mode=mode,  # type: ignore[arg-type]
        force=force,
        stop_event=stop_event,
        user_id=user_id,
        batch_uid=batch_uid,
    )
    loop = asyncio.get_running_loop()
    try:
        while True:
            if await request.is_disconnected():
                stop_event.set()
                break
            chunk = await loop.run_in_executor(None, _take_next_chunk, sync_iter)
            if chunk is None:
                break
            yield chunk
    finally:
        stop_event.set()


@router.get("", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> list[KnowledgeBase]:
    return db.execute(
        select(KnowledgeBase)
        .where(
            KnowledgeBase.enterprise_space_id == current_space.id,
            KnowledgeBase.status != "deleted",
        )
        .order_by(KnowledgeBase.created_at.desc())
    ).scalars().all()


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> KnowledgeBase:
    ensure_knowledge_base_name_unique(db, space_id=current_space.id, name=payload.name)
    create_data = apply_retrieval_defaults_to_payload(payload.model_dump())
    if create_data.get("kb_type") == "lightrag":
        create_data["graph_db_enabled"] = True
        config = dict(create_data.get("config") or {})
        lightrag_cfg = dict(config.get("lightrag") or {})
        lightrag_cfg.setdefault("default_query_mode", "mix")
        config["lightrag"] = lightrag_cfg
        create_data["config"] = config
    knowledge_base = KnowledgeBase(
        enterprise_space_id=current_space.id,
        **create_data,
        status="active",
        milvus_collection_name="",
    )
    db.add(knowledge_base)
    db.flush()
    knowledge_base.milvus_collection_name = build_collection_name(knowledge_base.enterprise_space_id, knowledge_base.id)
    if knowledge_base.vector_db_enabled or knowledge_base.kb_type == "lightrag":
        try:
            resolve_knowledge_base_milvus_dimension(
                db,
                knowledge_base=knowledge_base,
                persist=False,
            )
        except AppError:
            pass
    db.commit()
    db.refresh(knowledge_base)
    return knowledge_base


@router.post("/multi-search", response_model=MultiKnowledgeSearchResponse)
def search_documents_multi(
    payload: MultiKnowledgeSearchRequest,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    """跨多个知识库检索，结果按分数合并排序（与首页「知识检索」多选一致）。"""
    return search_knowledge_bases_multi(
        db,
        space_id=current_space.id,
        knowledge_base_ids=payload.knowledge_base_ids,
        payload=payload,
    )


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_base(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> KnowledgeBase:
    return get_knowledge_base_or_error(db, space_id=current_space.id, kb_id=kb_id)


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(
    kb_id: int,
    payload: KnowledgeBaseUpdate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> KnowledgeBase:
    knowledge_base = get_knowledge_base_or_error(db, space_id=current_space.id, kb_id=kb_id)
    update_data = payload.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"]:
        ensure_knowledge_base_name_unique(
            db,
            space_id=current_space.id,
            name=update_data["name"],
            exclude_kb_id=knowledge_base.id,
        )
    for field, value in update_data.items():
        setattr(knowledge_base, field, value)
    if "config" in update_data:
        cfg = update_data.get("config")
        if isinstance(cfg, dict):
            pdf_parser = cfg.get("pdf_parser")
            if pdf_parser is not None:
                allowed = {"opendataloader", "mineru", "docling"}
                if str(pdf_parser).strip().lower() not in allowed:
                    raise AppError(
                        status_code=400,
                        code="INVALID_PDF_PARSER",
                        message=f"pdf_parser 须为 {', '.join(sorted(allowed))} 之一",
                    )
            parsers = cfg.get("parsers")
            if isinstance(parsers, dict):
                from app.core.parser_config import validate_parsers_patch

                validate_parsers_patch(parsers)
            enrichment = cfg.get("enrichment")
            if isinstance(enrichment, dict):
                from app.core.parser_config import validate_enrichment_patch

                validate_enrichment_patch(enrichment)
    if "config" in update_data and knowledge_base.kb_type == "lightrag":
        from app.services.lightrag_engine import invalidate_lightrag_instance

        invalidate_lightrag_instance(knowledge_base.id)
    if "embedding_model_id" in update_data and (
        knowledge_base.vector_db_enabled or knowledge_base.kb_type == "lightrag"
    ):
        try:
            resolve_knowledge_base_milvus_dimension(
                db,
                knowledge_base=knowledge_base,
                persist=False,
            )
        except AppError:
            pass
    db.commit()
    db.refresh(knowledge_base)
    return knowledge_base


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_knowledge_base(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> Response:
    knowledge_base = get_knowledge_base_or_error(db, space_id=current_space.id, kb_id=kb_id)
    knowledge_base.status = "deleted"
    knowledge_base.name = build_deleted_knowledge_base_name(knowledge_base.name, knowledge_base.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{kb_id}/purge", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def purge_knowledge_base(
    kb_id: int,
    payload: KnowledgeBasePurgeRequest,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> Response:
    """
    彻底删除知识库（不可恢复）：需要二次确认（输入名称 + confirm=true）。
    会清理：
    - DB：knowledge_base、documents、chunks、neo4j_connection
    - Storage：backend/storage/knowledge_files/<space>/<kb>/...
    - Milvus：drop collection（若启用向量库）
    """
    knowledge_base = get_knowledge_base_or_error(
        db, space_id=current_space.id, kb_id=kb_id, include_deleted=True
    )
    if not payload.confirm:
        raise AppError(status_code=400, code="PURGE_CONFIRM_REQUIRED", message="请二次确认后再执行彻底删除")
    if payload.confirm_name.strip() != (knowledge_base.name or "").strip():
        raise AppError(status_code=400, code="PURGE_CONFIRM_NAME_MISMATCH", message="输入的知识库名称不匹配")

    # 1) 向量库：直接 drop collection（比逐条删更快，且彻底）
    if knowledge_base.vector_db_enabled and knowledge_base.milvus_collection_name:
        drop_collection_if_exists(
            host=settings.milvus_host,
            port=settings.milvus_port,
            collection_name=knowledge_base.milvus_collection_name,
            username=settings.milvus_username,
            password=settings.milvus_password,
        )

    # 2) 本地存储：删除该 KB 的存储目录（忽略不存在）
    backend_dir = Path(__file__).resolve().parents[3]
    storage_root = backend_dir / "storage" / "knowledge_files"
    kb_dir = storage_root / str(current_space.id) / str(kb_id)
    try:
        if kb_dir.exists():
            shutil.rmtree(kb_dir, ignore_errors=True)
    except Exception:
        # 文件系统清理失败不应阻塞 DB 删除（避免“删不掉”卡死）；保留为垃圾数据后续可人工清理
        pass

    opensearch_chunk_service.delete_by_knowledge_base_id(kb_id)

    # 3) DB：先删子表，再删 KB
    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_base_id == kb_id))
    db.execute(delete(KnowledgeDocument).where(KnowledgeDocument.knowledge_base_id == kb_id))
    db.execute(delete(Neo4jConnection).where(Neo4jConnection.knowledge_base_id == kb_id))
    db.execute(delete(KnowledgeBase).where(KnowledgeBase.id == kb_id, KnowledgeBase.enterprise_space_id == current_space.id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{kb_id}/stats", response_model=KnowledgeBaseStatsResponse)
def get_knowledge_base_statistics(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    knowledge_base = get_knowledge_base_or_error(db, space_id=current_space.id, kb_id=kb_id)
    return get_knowledge_base_stats(db, knowledge_base=knowledge_base)


@router.post("/{kb_id}/neo4j-connection", response_model=Neo4jConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_neo4j_connection(
    kb_id: int,
    payload: Neo4jConnectionCreate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> Neo4jConnection:
    get_knowledge_base_or_error(db, space_id=current_space.id, kb_id=kb_id, include_deleted=True)
    existing = db.execute(
        select(Neo4jConnection).where(Neo4jConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()
    if existing is not None:
        raise AppError(status_code=409, code="NEO4J_CONNECTION_ALREADY_EXISTS", message="该知识库已存在 Neo4j 连接")
    connection = Neo4jConnection(knowledge_base_id=kb_id, **payload.model_dump())
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


@router.get("/{kb_id}/neo4j-connection", response_model=Neo4jConnectionResponse)
def get_neo4j_connection(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> Neo4jConnection:
    get_knowledge_base_or_error(db, space_id=current_space.id, kb_id=kb_id, include_deleted=True)
    return get_neo4j_connection_or_error(db, knowledge_base_id=kb_id)


@router.patch("/{kb_id}/neo4j-connection", response_model=Neo4jConnectionResponse)
def update_neo4j_connection(
    kb_id: int,
    payload: Neo4jConnectionUpdate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> Neo4jConnection:
    get_knowledge_base_or_error(db, space_id=current_space.id, kb_id=kb_id, include_deleted=True)
    connection = get_neo4j_connection_or_error(db, knowledge_base_id=kb_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(connection, field, value)
    db.commit()
    db.refresh(connection)
    return connection


@router.delete("/{kb_id}/neo4j-connection", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_neo4j_connection(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> Response:
    get_knowledge_base_or_error(db, space_id=current_space.id, kb_id=kb_id, include_deleted=True)
    connection = get_neo4j_connection_or_error(db, knowledge_base_id=kb_id)
    db.delete(connection)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{kb_id}/neo4j-connection/test", response_model=ConnectionTestResponse)
def test_neo4j_connection_endpoint(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> ConnectionTestResponse:
    get_knowledge_base_or_error(db, space_id=current_space.id, kb_id=kb_id, include_deleted=True)
    connection = get_neo4j_connection_or_error(db, knowledge_base_id=kb_id)
    result = test_neo4j_connection(
        uri=connection.uri,
        username=connection.username,
        password=connection.password,
        database=connection.database,
    )
    if not result.success:
        raise AppError(status_code=502, code="NEO4J_CONNECTION_FAILED", message=result.message)
    return ConnectionTestResponse(
        success=True,
        message=result.message,
        response_time_ms=result.response_time_ms,
    )


@router.get("/{kb_id}/documents", response_model=KnowledgeDocumentListResponse)
def query_documents(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    document_status: str | None = Query(default=None, alias="status"),
    keyword: str | None = Query(default=None),
    file_ext: str | None = Query(
        default=None,
        description="按扩展名筛选，不含点；多个用逗号分隔，如 doc,docx",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    sort: str | None = Query(
        default=None,
        description="created_desc | created_asc | name_asc | updated_desc",
    ),
) -> dict:
    return list_documents(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        status=document_status,
        keyword=keyword,
        file_ext=file_ext,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@router.get("/{kb_id}/process-log/summary", response_model=KbProcessLogSummaryResponse)
def get_kb_process_log_summary(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    return kb_process_audit_service.get_process_log_summary(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
    )


@router.get("/{kb_id}/process-log/events", response_model=KbProcessLogEventListResponse)
def list_kb_process_log_events(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
) -> dict:
    return kb_process_audit_service.list_process_log_events(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        page=page,
        page_size=page_size,
        action=action,
        status=status,
        keyword=keyword,
    )


@router.get("/{kb_id}/process-log/events/{batch_id}/items", response_model=KbProcessLogBatchItemsResponse)
def list_kb_process_log_batch_items(
    kb_id: int,
    batch_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    return kb_process_audit_service.list_process_log_batch_items(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        batch_id=batch_id,
    )


@router.post("/{kb_id}/process-log/upload-batch", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def record_kb_upload_batch(
    kb_id: int,
    payload: UploadBatchAuditRequest,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> Response:
    kb_process_audit_service.record_upload_batch(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        user_id=current_user.id,
        batch_uid=payload.batch_uid,
        items=[item.model_dump() for item in payload.items],
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{kb_id}/process-log/start-batch", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def start_kb_process_batch(
    kb_id: int,
    payload: StartProcessBatchRequest,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> Response:
    kb_process_audit_service.start_process_batch(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        user_id=current_user.id,
        batch_uid=payload.batch_uid,
        action=payload.action,
        force=payload.force,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{kb_id}/documents/upload", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_endpoint(
    kb_id: int,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    chunk_size: int | None = Form(default=None),
    chunk_overlap: int | None = Form(default=None),
    skip_if_duplicate: bool = Form(default=False),
) -> dict:
    file_bytes = await file.read()
    filename = file.filename or "document.txt"
    return upload_document(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        file_name=filename,
        file_bytes=file_bytes,
        mime_type=file.content_type,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        skip_if_duplicate=skip_if_duplicate,
        user_id=current_user.id,
        record_audit=False,
    )


@router.post("/{kb_id}/documents/{document_id}/parse", response_model=KnowledgeDocumentResponse)
def parse_document_endpoint(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    embedding_model_id: int | None = Query(default=None),
) -> dict:
    return process_document(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        document_id=document_id,
        embedding_model_id=embedding_model_id,
    )


@router.post("/{kb_id}/documents/{document_id}/parse-stream")
async def parse_document_stream(
    request: Request,
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    embedding_model_id: int | None = Query(default=None),
    force: bool = Query(default=False),
    batch_id: str | None = Query(default=None),
) -> StreamingResponse:
    """Server-Sent Events：解析过程中实时输出日志，完成后在 data 中附带 document。"""
    return StreamingResponse(
        _stream_document_process_sse(
            request,
            space_id=current_space.id,
            kb_id=kb_id,
            document_id=document_id,
            embedding_model_id=embedding_model_id,
            mode="parse",
            force=force,
            user_id=current_user.id,
            batch_uid=batch_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{kb_id}/documents/{document_id}", response_model=KnowledgeDocumentResponse)
def get_document(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    return get_document_detail(db, space_id=current_space.id, kb_id=kb_id, document_id=document_id)


@router.patch("/{kb_id}/documents/{document_id}/chunking-config", response_model=KnowledgeDocumentResponse)
def update_document_chunking_config_endpoint(
    kb_id: int,
    document_id: int,
    payload: KnowledgeDocumentChunkingConfigUpdate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    return update_document_chunking_config(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        document_id=document_id,
        chunking_config=payload.chunking_config,
    )


@router.get("/{kb_id}/documents/{document_id}/parse-log", response_model=KnowledgeDocumentParseLogResponse)
def get_document_parse_log_endpoint(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    return get_document_parse_log(db, space_id=current_space.id, kb_id=kb_id, document_id=document_id)


@router.get("/{kb_id}/documents/{document_id}/file")
def get_document_original_file(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> FileResponse:
    """返回原始上传文件，用于浏览器内预览（Content-Disposition: inline）。"""
    document = get_document_or_error(db, space_id=current_space.id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    path = resolve_original_file_path(document)
    if not path:
        logger.warning(
            "原始文件不可用 doc_id=%s kb_id=%s space_id=%s storage_path=%r",
            document.id,
            kb_id,
            current_space.id,
            document.storage_path,
        )
        raise AppError(status_code=404, code="DOCUMENT_FILE_NOT_FOUND", message="原始文件不存在")
    media_type = document.mime_type or mimetypes.guess_type(document.file_name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        filename=document.file_name,
        content_disposition_type="inline",
    )


@router.get("/{kb_id}/documents/{document_id}/mineru-markdown")
def get_document_mineru_markdown(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> FileResponse:
    """解析时由 MinerU 生成的 Markdown 侧车文件（与商业 MinerU 右侧 Markdown 视图同源）。"""
    document = get_document_or_error(db, space_id=current_space.id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    orig = resolve_original_file_path(document)
    if not orig:
        raise AppError(status_code=404, code="DOCUMENT_FILE_NOT_FOUND", message="原始文件不存在")
    path = orig.parent / MINERU_VIEW_MD_FILENAME
    if not path.is_file():
        raise AppError(
            status_code=404,
            code="MINERU_MARKDOWN_NOT_FOUND",
            message="暂无 MinerU Markdown：请使用当前版本重新解析或重建索引（MinerU 引擎解析的文档会生成）",
        )
    return FileResponse(
        path,
        media_type="text/markdown; charset=utf-8",
        filename="mineru.md",
        content_disposition_type="inline",
    )


@router.get("/{kb_id}/documents/{document_id}/mineru-content-list")
def get_document_mineru_content_list(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> FileResponse:
    """MinerU content_list JSON（与商业 MinerU JSON 视图同源）。"""
    document = get_document_or_error(db, space_id=current_space.id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    orig = resolve_original_file_path(document)
    if not orig:
        raise AppError(status_code=404, code="DOCUMENT_FILE_NOT_FOUND", message="原始文件不存在")
    path = orig.parent / MINERU_VIEW_CL_FILENAME
    if not path.is_file():
        raise AppError(
            status_code=404,
            code="MINERU_CONTENT_LIST_NOT_FOUND",
            message="暂无 MinerU JSON：请使用当前版本重新解析或重建索引（MinerU 引擎解析的文档会生成）",
        )
    return FileResponse(
        path,
        media_type="application/json; charset=utf-8",
        filename="mineru_content_list.json",
        content_disposition_type="inline",
    )


@router.get("/{kb_id}/documents/{document_id}/docx-markdown")
def get_document_docx_markdown(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Word 解析侧车 Markdown（docx_markdown.md）。"""
    document = get_document_or_error(db, space_id=current_space.id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    orig = resolve_original_file_path(document)
    if not orig:
        raise AppError(status_code=404, code="DOCUMENT_FILE_NOT_FOUND", message="原始文件不存在")
    path = orig.parent / DOCX_VIEW_MD_FILENAME
    if not path.is_file():
        raise AppError(
            status_code=404,
            code="DOCX_MARKDOWN_NOT_FOUND",
            message="暂无 Word Markdown：请使用当前版本重新解析或重建索引",
        )
    return FileResponse(
        path,
        media_type="text/markdown; charset=utf-8",
        filename="docx.md",
        content_disposition_type="inline",
    )


@router.get("/{kb_id}/documents/{document_id}/docx-content-list")
def get_document_docx_content_list(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Word 解析 content_list JSON（docx_content_list.json）。"""
    document = get_document_or_error(db, space_id=current_space.id, kb_id=kb_id, document_id=document_id)
    if document.status == KnowledgeDocumentStatus.DELETED.value:
        raise AppError(status_code=404, code="DOCUMENT_NOT_FOUND", message="文档不存在")
    orig = resolve_original_file_path(document)
    if not orig:
        raise AppError(status_code=404, code="DOCUMENT_FILE_NOT_FOUND", message="原始文件不存在")
    path = orig.parent / DOCX_VIEW_CL_FILENAME
    if not path.is_file():
        raise AppError(
            status_code=404,
            code="DOCX_CONTENT_LIST_NOT_FOUND",
            message="暂无 Word JSON：请使用当前版本重新解析或重建索引",
        )
    return FileResponse(
        path,
        media_type="application/json; charset=utf-8",
        filename="docx_content_list.json",
        content_disposition_type="inline",
    )


@router.delete("/{kb_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_document(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    batch_id: str | None = Query(default=None),
) -> Response:
    delete_document_asset(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        document_id=document_id,
        user_id=current_user.id,
        batch_uid=batch_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{kb_id}/documents/{document_id}/reindex", response_model=KnowledgeDocumentResponse)
def reindex_document_endpoint(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    embedding_model_id: int | None = Query(default=None),
) -> dict:
    return reindex_document(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        document_id=document_id,
        embedding_model_id=embedding_model_id,
    )


@router.post("/{kb_id}/documents/{document_id}/reindex-stream")
async def reindex_document_stream(
    request: Request,
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    embedding_model_id: int | None = Query(default=None),
    force: bool = Query(default=False),
    batch_id: str | None = Query(default=None),
) -> StreamingResponse:
    """Server-Sent Events：重建索引时实时输出日志。"""
    return StreamingResponse(
        _stream_document_process_sse(
            request,
            space_id=current_space.id,
            kb_id=kb_id,
            document_id=document_id,
            embedding_model_id=embedding_model_id,
            mode="reindex",
            force=force,
            user_id=current_user.id,
            batch_uid=batch_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{kb_id}/documents/{document_id}/cancel-process", response_model=KnowledgeDocumentResponse)
def cancel_document_process_endpoint(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    current_user: CurrentUser,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    """取消进行中的文档解析/重建任务。"""
    return cancel_document_process(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        document_id=document_id,
        user_id=current_user.id,
    )


@router.get("/{kb_id}/documents/{document_id}/chunks", response_model=KnowledgeChunkListResponse)
def get_document_chunks(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, description="按切片正文模糊匹配"),
    chunk_view: Literal["lightrag", "parse"] = Query(
        default="lightrag",
        description="图知识库：lightrag=LightRAG 索引大段；parse=解析切片（knowledge_chunk 表）。经典库忽略此参数。",
    ),
) -> dict:
    return list_document_chunks(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        document_id=document_id,
        page=page,
        page_size=page_size,
        keyword=keyword,
        chunk_view=chunk_view,
    )


@router.get("/{kb_id}/chunks/{chunk_id}", response_model=KnowledgeChunkResponse)
def get_knowledge_chunk_endpoint(
    kb_id: int,
    chunk_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    """按 ID 获取切片正文（对话引文点击查看等）。"""
    return get_knowledge_chunk_serialized(db, space_id=current_space.id, kb_id=kb_id, chunk_id=chunk_id)


@router.get("/{kb_id}/chunks/{chunk_id}/source-context", response_model=ChunkSourceContextResponse)
def get_knowledge_chunk_source_context_endpoint(
    kb_id: int,
    chunk_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    context_chars: int = Query(default=320, ge=80, le=1200),
) -> dict:
    """切片在解析全文中的定位片段（含前后上下文），供检索结果详情展示。"""
    return get_chunk_source_context_serialized(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        chunk_id=chunk_id,
        context_chars=context_chars,
    )


@router.patch("/{kb_id}/chunks/{chunk_id}", response_model=KnowledgeChunkResponse)
def update_knowledge_chunk_enrichment_endpoint(
    kb_id: int,
    chunk_id: int,
    payload: KnowledgeChunkEnrichmentUpdate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    """更新切片关键词与假设问题，并增量重算向量/检索索引。"""
    return update_chunk_enrichment(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        chunk_id=chunk_id,
        keywords=payload.keywords,
        questions=payload.questions,
    )


@router.post(
    "/{kb_id}/chunks/{chunk_id}/regenerate-enrichment",
    response_model=KnowledgeChunkEnrichmentRegenerateResponse,
)
def regenerate_knowledge_chunk_enrichment_endpoint(
    kb_id: int,
    chunk_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    """调用入库增强 LLM 为单块生成关键词与假设问题（不写库）。"""
    return regenerate_chunk_enrichment(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        chunk_id=chunk_id,
    )


@router.post("/{kb_id}/search", response_model=KnowledgeSearchResponse)
def search_documents(
    kb_id: int,
    payload: KnowledgeSearchRequest,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    return search_knowledge_base(db, space_id=current_space.id, kb_id=kb_id, payload=payload)


@router.post("/{kb_id}/graph-search", response_model=GraphSearchResponse)
def graph_search(
    kb_id: int,
    payload: GraphSearchRequest,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> GraphSearchResponse:
    kb = get_knowledge_base_or_error(db, space_id=current_space.id, kb_id=kb_id)
    ensure_lightrag_kb(kb)
    data = query_graph_kb(
        db,
        knowledge_base=kb,
        query=payload.query,
        mode=payload.mode,
        top_k=payload.top_k,
        chunk_top_k=payload.chunk_top_k,
        include_references=payload.include_references,
    )
    return GraphSearchResponse(**data)


@router.post("/{kb_id}/chunking/preview", response_model=KnowledgeDocumentChunkingPreviewResponse)
def preview_chunking(
    kb_id: int,
    payload: KnowledgeDocumentChunkingPreviewRequest,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> dict:
    return preview_document_chunking(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        document_id=payload.document_id,
        chunking_config=payload.chunking_config,
        max_pages=payload.max_pages,
        max_chars=payload.max_chars,
        max_chunks=payload.max_chunks,
    )
