from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enterprise_space_context import CurrentSpace, RequireMembership
from app.core.errors import AppError
from app.core.neo4j_client import test_neo4j_connection
from app.db.session import get_db
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
    KnowledgeChunkListResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentParseLogResponse,
    KnowledgeDocumentChunkingConfigUpdate,
    KnowledgeDocumentChunkingPreviewRequest,
    KnowledgeDocumentChunkingPreviewResponse,
    KnowledgeDocumentResponse,
)
from app.schemas.retrieval import KnowledgeSearchRequest, KnowledgeSearchResponse
from app.services.knowledge_base_service import (
    build_deleted_knowledge_base_name,
    build_collection_name,
    ensure_knowledge_base_name_unique,
    get_knowledge_base_or_error,
    get_knowledge_base_stats,
    get_neo4j_connection_or_error,
)
from app.services.knowledge_document_service import (
    delete_document_asset,
    get_document_detail,
    get_document_or_error,
    get_document_parse_log,
    update_document_chunking_config,
    preview_document_chunking,
    iter_document_process_sse_events,
    list_document_chunks,
    list_documents,
    process_document,
    reindex_document,
    upload_document,
)
from app.services.retrieval_service import search_knowledge_base

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-base-management"])
settings = get_settings()


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
    knowledge_base = KnowledgeBase(
        enterprise_space_id=current_space.id,
        **payload.model_dump(),
        status="active",
        milvus_collection_name="",
    )
    db.add(knowledge_base)
    db.flush()
    knowledge_base.milvus_collection_name = build_collection_name(knowledge_base.enterprise_space_id, knowledge_base.id)
    db.commit()
    db.refresh(knowledge_base)
    return knowledge_base


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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
) -> dict:
    return list_documents(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        status=document_status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )


@router.post("/{kb_id}/documents/upload", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_endpoint(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    chunk_size: int | None = Form(default=None),
    chunk_overlap: int | None = Form(default=None),
) -> dict:
    file_bytes = await file.read()
    return upload_document(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        file_name=file.filename or "document.txt",
        file_bytes=file_bytes,
        mime_type=file.content_type,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
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
def parse_document_stream(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    embedding_model_id: int | None = Query(default=None),
) -> StreamingResponse:
    """Server-Sent Events：解析过程中实时输出日志，完成后在 data 中附带 document。"""
    return StreamingResponse(
        iter_document_process_sse_events(
            space_id=current_space.id,
            kb_id=kb_id,
            document_id=document_id,
            embedding_model_id=embedding_model_id,
            mode="parse",
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
    if not document.storage_path:
        raise AppError(status_code=404, code="DOCUMENT_FILE_NOT_FOUND", message="原始文件不存在")
    path = Path(document.storage_path)
    if not path.is_file():
        raise AppError(status_code=404, code="DOCUMENT_FILE_NOT_FOUND", message="原始文件不存在")
    media_type = document.mime_type or mimetypes.guess_type(document.file_name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        filename=document.file_name,
        content_disposition_type="inline",
    )


@router.delete("/{kb_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_document(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Session = Depends(get_db),
) -> Response:
    delete_document_asset(db, space_id=current_space.id, kb_id=kb_id, document_id=document_id)
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
def reindex_document_stream(
    kb_id: int,
    document_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    embedding_model_id: int | None = Query(default=None),
) -> StreamingResponse:
    """Server-Sent Events：重建索引时实时输出日志。"""
    return StreamingResponse(
        iter_document_process_sse_events(
            space_id=current_space.id,
            kb_id=kb_id,
            document_id=document_id,
            embedding_model_id=embedding_model_id,
            mode="reindex",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
) -> dict:
    return list_document_chunks(
        db,
        space_id=current_space.id,
        kb_id=kb_id,
        document_id=document_id,
        page=page,
        page_size=page_size,
        keyword=keyword,
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
