"""多库检索对图知识库（LightRAG）的合并。"""

from unittest.mock import MagicMock, patch

from app.models.knowledge_base import KnowledgeBase
from app.schemas.retrieval import KnowledgeSearchRequest
from app.services.retrieval_service import (
    _merge_multi_kb_results,
    _merge_multi_kb_results_fair,
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


def test_serialize_lightrag_search_results_prefers_multiple_chunks():
    kb = KnowledgeBase(id=7, enterprise_space_id=1, name="刑法（图）", kb_type="lightrag")
    graph_data = {
        "citations": [
            {
                "ref": 1,
                "document_name": "刑法.pdf",
                "document_id": 12,
                "chunk_id": "chunk-a",
                "content": "第一条 …",
            }
        ],
        "chunks": [
            {"chunk_id": "chunk-a", "score": 0.9, "content": "第一条 …", "file_path": "刑法.pdf"},
            {"chunk_id": "chunk-b", "score": 0.8, "content": "第二条 …", "file_path": "刑法.pdf"},
            {"chunk_id": "chunk-c", "score": 0.7, "content": "第三条 …", "file_path": "刑法.pdf"},
        ],
    }

    rows = _serialize_lightrag_search_results(knowledge_base=kb, graph_data=graph_data, limit=5)

    assert len(rows) == 3
    assert [row["content"] for row in rows] == ["第一条 …", "第二条 …", "第三条 …"]


def test_merge_multi_kb_results_reserves_each_knowledge_base():
    graph_rows = [
        {
            "knowledge_base_id": 2,
            "chunk_id": index,
            "document_id": 1,
            "score": 0.99 - index * 0.01,
            "content": f"graph chunk {index}",
        }
        for index in range(5)
    ]
    vector_rows = [
        {
            "knowledge_base_id": 1,
            "chunk_id": 100 + index,
            "document_id": 2,
            "score": 0.45 - index * 0.01,
            "content": f"vector chunk {index}",
        }
        for index in range(5)
    ]
    merged = _merge_multi_kb_results(graph_rows + vector_rows, kb_ids=[1, 2], limit=5)

    assert len(merged) == 5
    assert {row["knowledge_base_id"] for row in merged} == {1, 2}


def test_merge_multi_kb_results_fair_balances_types_when_graph_scores_higher():
    graph_rows = [
        {
            "knowledge_base_id": 2,
            "chunk_id": index,
            "document_id": 1,
            "metadata": {"source": "lightrag"},
            "score": 0.99 - index * 0.01,
            "content": f"graph chunk {index}",
        }
        for index in range(5)
    ]
    vector_rows = [
        {
            "knowledge_base_id": 1,
            "chunk_id": 100 + index,
            "document_id": 2,
            "metadata": {"source": "vector"},
            "score": 0.45 - index * 0.01,
            "content": f"vector chunk {index}",
        }
        for index in range(5)
    ]
    merged, meta = _merge_multi_kb_results_fair(graph_rows + vector_rows, kb_ids=[1, 2], limit=5)

    assert len(merged) == 5
    assert {row["knowledge_base_id"] for row in merged} == {1, 2}
    assert meta["strategy"] == "auto_fair"
    assert meta["type_breakdown"]["classic"] >= 1
    assert meta["type_breakdown"]["lightrag"] >= 1


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
                "ref": index + 1,
                "document_name": f"graph-doc-{index}",
                "document_id": 4 + index,
                "chunk_id": f"g{index}",
                "content": f"图库结果 {index}",
            }
            for index in range(8)
        ],
        "chunks": [
            {"chunk_id": f"g{index}", "score": 0.9 - index * 0.05, "content": f"图库结果 {index}"}
            for index in range(8)
        ],
    }

    db = MagicMock()
    data = search_knowledge_bases_multi(
        db,
        space_id=1,
        knowledge_base_ids=[1, 2],
        payload=KnowledgeSearchRequest(query="医保最新政策"),
        vector_top_k=8,
        lightrag_top_k=8,
        merge_top_k=5,
    )

    assert data["total"] == 5
    assert len(data["path_results"]) == 2
    assert data["merge_meta"]["strategy"] == "auto_fair"
    assert data["merge_meta"]["vector_top_k"] == 8
    assert data["merge_meta"]["lightrag_top_k"] == 8
    assert data["merge_meta"]["merge_top_k"] == 5
    graph_path = next(row for row in data["path_results"] if row["kb_type"] == "lightrag")
    assert graph_path["recalled_count"] == 8
    assert len(graph_path["candidates"]) == 8
    mock_query_graph.assert_called_once()
    mock_search_one.assert_called_once()
    assert mock_query_graph.call_args.kwargs["top_k"] == 8
    assert mock_search_one.call_args[1]["payload"].top_k == 8
