from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enterprise_space_context import CurrentSpace, RequireMembership
from app.core.milvus_client import test_milvus_connection as test_milvus_conn
from app.core.neo4j_client import test_neo4j_connection as test_neo4j_conn
from app.db.session import get_db
from app.models.knowledge_base import KnowledgeBase, MilvusConnection, Neo4jConnection
from app.schemas.knowledge_base import (
    ConnectionTestResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    MilvusConnectionCreate,
    MilvusConnectionResponse,
    MilvusConnectionUpdate,
    Neo4jConnectionCreate,
    Neo4jConnectionResponse,
    Neo4jConnectionUpdate,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-base-management"])


def _get_db() -> Session:
    """获取数据库会话"""
    db = next(get_db())
    try:
        return db
    finally:
        pass


# ============== Knowledge Base CRUD ==============

@router.get("", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> list[KnowledgeBaseResponse]:
    """列出当前企业空间下的所有知识库"""
    knowledge_bases = db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.enterprise_space_id == current_space.id)
        .where(KnowledgeBase.status != "deleted")
        .order_by(KnowledgeBase.created_at.desc())
    ).scalars().all()

    return knowledge_bases


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    kb_data: KnowledgeBaseCreate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> KnowledgeBaseResponse:
    """创建新的知识库"""
    existing = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.name == kb_data.name,
            KnowledgeBase.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"知识库 '{kb_data.name}' 已存在",
        )

    kb = KnowledgeBase(
        enterprise_space_id=current_space.id,
        name=kb_data.name,
        description=kb_data.description,
        status="active",
        vector_db_enabled=kb_data.vector_db_enabled,
        graph_db_enabled=kb_data.graph_db_enabled,
        config=kb_data.config,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_base(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> KnowledgeBaseResponse:
    """获取指定知识库详情"""
    kb = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或不属于当前企业空间",
        )
    return kb


@router.patch("/{kb_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(
    kb_id: int,
    kb_data: KnowledgeBaseUpdate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> KnowledgeBaseResponse:
    """更新知识库配置"""
    kb = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或不属于当前企业空间",
        )

    update_data = kb_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(kb, field, value)

    db.commit()
    db.refresh(kb)
    return kb


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> None:
    """删除知识库（软删除）"""
    kb = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或不属于当前企业空间",
        )

    kb.status = "deleted"
    db.commit()


# ============== Milvus Connection ==============

@router.post("/{kb_id}/milvus-connection", response_model=MilvusConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_milvus_connection(
    kb_id: int,
    conn_data: MilvusConnectionCreate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> MilvusConnectionResponse:
    """创建 Milvus 连接配置"""
    kb = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或不属于当前企业空间",
        )

    existing = db.execute(
        select(MilvusConnection).where(MilvusConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该知识库已存在 Milvus 连接",
        )

    collection_name = f"kb_{kb_id}_{kb.name.replace(' ', '_').lower()}"
    conn = MilvusConnection(
        knowledge_base_id=kb_id,
        host=conn_data.host,
        port=conn_data.port,
        username=conn_data.username,
        password=conn_data.password,
        collection_name=collection_name,
        dimension=conn_data.dimension,
        metric_type=conn_data.metric_type,
        config=conn_data.config,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.get("/{kb_id}/milvus-connection", response_model=MilvusConnectionResponse)
def get_milvus_connection(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> MilvusConnectionResponse:
    """获取 Milvus 连接配置"""
    conn = db.execute(
        select(MilvusConnection).where(MilvusConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()

    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milvus 连接不存在",
        )
    return conn


@router.patch("/{kb_id}/milvus-connection", response_model=MilvusConnectionResponse)
def update_milvus_connection(
    kb_id: int,
    conn_data: MilvusConnectionUpdate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> MilvusConnectionResponse:
    """更新 Milvus 连接配置"""
    conn = db.execute(
        select(MilvusConnection).where(MilvusConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()

    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milvus 连接不存在",
        )

    update_data = conn_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(conn, field, value)

    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/{kb_id}/milvus-connection", status_code=status.HTTP_204_NO_CONTENT)
def delete_milvus_connection(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> None:
    """删除 Milvus 连接配置"""
    conn = db.execute(
        select(MilvusConnection).where(MilvusConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()

    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milvus 连接不存在",
        )

    db.delete(conn)
    db.commit()


@router.post("/{kb_id}/milvus-connection/test", response_model=ConnectionTestResponse)
def test_milvus_connection(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> ConnectionTestResponse:
    """测试 Milvus 连接"""
    conn = db.execute(
        select(MilvusConnection).where(MilvusConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()

    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Milvus 连接不存在",
        )

    result = test_milvus_conn(
        host=conn.host,
        port=conn.port,
        username=conn.username,
        password=conn.password,
    )

    return ConnectionTestResponse(
        success=result.success,
        message=result.message,
        response_time_ms=result.response_time_ms,
    )


# ============== Neo4j Connection ==============

@router.post("/{kb_id}/neo4j-connection", response_model=Neo4jConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_neo4j_connection(
    kb_id: int,
    conn_data: Neo4jConnectionCreate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> Neo4jConnectionResponse:
    """创建 Neo4j 连接配置"""
    kb = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.enterprise_space_id == current_space.id,
        )
    ).scalar_one_or_none()

    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="知识库不存在或不属于当前企业空间",
        )

    existing = db.execute(
        select(Neo4jConnection).where(Neo4jConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该知识库已存在 Neo4j 连接",
        )

    conn = Neo4jConnection(
        knowledge_base_id=kb_id,
        uri=conn_data.uri,
        username=conn_data.username,
        password=conn_data.password,
        database=conn_data.database,
        config=conn_data.config,
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.get("/{kb_id}/neo4j-connection", response_model=Neo4jConnectionResponse)
def get_neo4j_connection(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> Neo4jConnectionResponse:
    """获取 Neo4j 连接配置"""
    conn = db.execute(
        select(Neo4jConnection).where(Neo4jConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()

    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Neo4j 连接不存在",
        )
    return conn


@router.patch("/{kb_id}/neo4j-connection", response_model=Neo4jConnectionResponse)
def update_neo4j_connection(
    kb_id: int,
    conn_data: Neo4jConnectionUpdate,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> Neo4jConnectionResponse:
    """更新 Neo4j 连接配置"""
    conn = db.execute(
        select(Neo4jConnection).where(Neo4jConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()

    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Neo4j 连接不存在",
        )

    update_data = conn_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(conn, field, value)

    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/{kb_id}/neo4j-connection", status_code=status.HTTP_204_NO_CONTENT)
def delete_neo4j_connection(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> None:
    """删除 Neo4j 连接配置"""
    conn = db.execute(
        select(Neo4jConnection).where(Neo4jConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()

    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Neo4j 连接不存在",
        )

    db.delete(conn)
    db.commit()


@router.post("/{kb_id}/neo4j-connection/test", response_model=ConnectionTestResponse)
def test_neo4j_connection(
    kb_id: int,
    current_space: CurrentSpace,
    membership: RequireMembership,
    db: Any = Depends(_get_db),
) -> ConnectionTestResponse:
    """测试 Neo4j 连接"""
    conn = db.execute(
        select(Neo4jConnection).where(Neo4jConnection.knowledge_base_id == kb_id)
    ).scalar_one_or_none()

    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Neo4j 连接不存在",
        )

    result = test_neo4j_conn(
        uri=conn.uri,
        username=conn.username,
        password=conn.password,
        database=conn.database,
    )

    return ConnectionTestResponse(
        success=result.success,
        message=result.message,
        response_time_ms=result.response_time_ms,
    )
