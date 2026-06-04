"""知识库创建：Embedding 探测与同名冲突。"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseStatus
from app.services.knowledge_base_service import (
    apply_embedding_probe_on_create,
    ensure_knowledge_base_embedding_available,
    raise_if_knowledge_base_name_conflict,
)


def test_raise_if_knowledge_base_name_conflict_maps_to_409():
    exc = IntegrityError("insert", {}, Exception('duplicate key value violates unique constraint "uq_knowledge_base_space_name"'))
    with pytest.raises(AppError) as err:
        raise_if_knowledge_base_name_conflict(exc)
    assert err.value.status_code == 409
    assert err.value.code == "KNOWLEDGE_BASE_ALREADY_EXISTS"
    assert "同名知识库已存在" in err.value.message


def test_apply_embedding_probe_on_create_success():
    db = MagicMock()
    kb = KnowledgeBase(
        enterprise_space_id=1,
        name="test",
        status=KnowledgeBaseStatus.ACTIVE.value,
        kb_type="classic",
        vector_db_enabled=True,
        graph_db_enabled=False,
        milvus_collection_name="kb_1_1_chunks",
        milvus_dimension=1536,
        milvus_metric_type="COSINE",
        default_chunk_size=512,
        default_chunk_overlap=50,
        default_retrieval_mode="hybrid",
        default_top_k=5,
    )
    with patch(
        "app.services.knowledge_base_service.resolve_knowledge_base_milvus_dimension",
        return_value=1024,
    ) as probe:
        warning = apply_embedding_probe_on_create(db, knowledge_base=kb)
    assert warning is None
    assert kb.status == KnowledgeBaseStatus.ACTIVE.value
    assert kb.config["embedding_probe"]["ok"] is True
    probe.assert_called_once()


def test_apply_embedding_probe_on_create_failure_sets_status():
    db = MagicMock()
    kb = KnowledgeBase(
        enterprise_space_id=1,
        name="test",
        status=KnowledgeBaseStatus.ACTIVE.value,
        kb_type="lightrag",
        vector_db_enabled=True,
        graph_db_enabled=True,
        milvus_collection_name="kb_1_1_chunks",
        milvus_dimension=1536,
        milvus_metric_type="COSINE",
        default_chunk_size=512,
        default_chunk_overlap=50,
        default_retrieval_mode="hybrid",
        default_top_k=5,
    )
    with patch(
        "app.services.knowledge_base_service.resolve_knowledge_base_milvus_dimension",
        side_effect=AppError(status_code=502, code="EMBEDDING_REQUEST_FAILED", message="GPU 繁忙"),
    ):
        warning = apply_embedding_probe_on_create(db, knowledge_base=kb)
    assert warning is not None
    assert "GPU 繁忙" in warning
    assert kb.status == KnowledgeBaseStatus.EMBEDDING_UNAVAILABLE.value
    assert kb.config["embedding_probe"]["ok"] is False


def test_ensure_knowledge_base_embedding_available_blocks_parse():
    kb = KnowledgeBase(
        enterprise_space_id=1,
        name="test",
        status=KnowledgeBaseStatus.EMBEDDING_UNAVAILABLE.value,
        kb_type="classic",
        vector_db_enabled=True,
        graph_db_enabled=False,
        milvus_collection_name="kb_1_1_chunks",
        milvus_dimension=1536,
        milvus_metric_type="COSINE",
        default_chunk_size=512,
        default_chunk_overlap=50,
        default_retrieval_mode="hybrid",
        default_top_k=5,
        config={"embedding_probe": {"ok": False, "message": "timeout"}},
    )
    with pytest.raises(AppError) as err:
        ensure_knowledge_base_embedding_available(kb)
    assert err.value.code == "EMBEDDING_MODEL_UNAVAILABLE"
