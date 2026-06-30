from app.services.agentic_rag.nodes import _build_citations, _citation_source_from_item


def test_citation_source_from_item() -> None:
    assert _citation_source_from_item({"metadata": {"source": "lightrag"}}) == "graph"
    assert _citation_source_from_item({"source": "graph"}) == "graph"
    assert _citation_source_from_item({"source": "vector"}) == "vector"
    assert _citation_source_from_item({}) == "vector"


def test_build_citations_sets_graph_and_vector_sources() -> None:
    cites = _build_citations(
        [
            {
                "document_name": "刑法",
                "chunk_id": 12,
                "metadata": {"source": "lightrag"},
                "content": "图库片段",
            },
            {
                "document_name": "医保制度",
                "chunk_id": 99,
                "source": "vector",
                "content": "向量片段",
            },
        ]
    )
    assert cites[0]["source"] == "graph"
    assert cites[1]["source"] == "vector"
