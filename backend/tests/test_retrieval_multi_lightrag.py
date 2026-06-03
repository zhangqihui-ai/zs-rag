"""多库检索对图知识库（LightRAG）的合并。"""

from unittest.mock import MagicMock, patch

from app.models.knowledge_base import KnowledgeBase
from app.schemas.retrieval import KnowledgeSearchRequest
from app.services.retrieval_service import (
    _serialize_lightrag_search_results,
    search_knowledge_bases_multi,
)


def test_serialize_lightrag_search_results_from_citations():
    kb = KnowledgeBase(id=7, enterprise_space_id=1, name="医疗知识库（图）", kb_type="lightrag")
    graph_data = {
        "citations": [
            {
                "ref": 1,
                "document_name": "policy.pdf",
                "document_id": 12,
                "chunk_id": "chunk-abc",
                "knowledge_base_id": 7,
                "content": "医保最新政策正文片段",
            }
        ],
        "chunks": [{"chunk_id": "chunk-abc", "score": 0.88, "content": "医保最新政策正文片段"}],
    }

    rows = _serialize_lightrag_search_results(knowledge_base=kb, graph_data=graph_data, limit=5)

    assert len(rows) == 1
    assert rows[0]["document_name"] == "policy.pdf"
    assert rows[0]["knowledge_base_name"] == "医疗知识库（图）"
    assert rows[0]["score"] == 0.88
    assert rows[0]["metadata"]["source"] == "lightrag"
    assert rows[0]["chunk_uid"] == "lightrag:7:chunk-abc"


@patch("app.services.lightrag_engine.query_graph_kb")
@patch("app.services.retrieval_service.search_knowledge_base")
@patch("app.services.retrieval_service.get_knowledge_base_or_error")
def test_search_knowledge_bases_multi_merges_classic_and_lightrag(
    mock_get_kb,
    mock_search_one,
    mock_query_graph,
):
    classic_kb = KnowledgeBase(
        id=1,
        enterprise_space_id=1,
        name="医疗知识库mineru",
        kb_type="classic",
        default_retrieval_mode="hybrid",
        default_top_k=5,
    )
    graph_kb = KnowledgeBase(
        id=2,
        enterprise_space_id=1,
        name="医疗知识库（图）",
        kb_type="lightrag",
        default_retrieval_mode="hybrid",
        default_top_k=5,
    )

    def _get_kb(_db, *, space_id, kb_id):
        return classic_kb if kb_id == 1 else graph_kb

    mock_get_kb.side_effect = _get_kb
    mock_search_one.return_value = {
        "mode": "hybrid",
        "results": [
            {
                "chunk_id": 10,
                "chunk_uid": "classic-1",
                "document_id": 3,
                "document_name": "vector-doc",
                "chunk_index": 0,
                "content": "向量库结果",
                "score": 0.3,
                "citation": {"document_name": "vector-doc", "chunk_index": 0},
            }
        ],
    }
    mock_query_graph.return_value = {
        "citations": [
            {
                "ref": 1,
                "document_name": "graph-doc",
                "document_id": 4,
                "chunk_id": "g1",
                "content": "图库结果",
            }
        ],
        "chunks": [{"chunk_id": "g1", "score": 0.9, "content": "图库结果"}],
    }

    db = MagicMock()
    data = search_knowledge_bases_multi(
        db,
        space_id=1,
        knowledge_base_ids=[1, 2],
        payload=KnowledgeSearchRequest(query="医保最新政策"),
    )

    assert data["total"] == 2
    assert [row["knowledge_base_name"] for row in data["results"]] == ["医疗知识库（图）", "医疗知识库mineru"]
    mock_query_graph.assert_called_once()
    mock_search_one.assert_called_once()
