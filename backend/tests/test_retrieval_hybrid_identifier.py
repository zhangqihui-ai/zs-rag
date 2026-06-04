"""混合检索：事项编码等字母数字精确查询。"""

from app.services.retrieval_service import (
    _dominant_identifier_in_query,
    _filter_hybrid_channel_candidates,
    _hybrid_cross_domain_guard,
    _layered_keyword_match_score,
    _min_keyword_hybrid_score_for_query,
    _rescore_keyword_candidates,
)


class _Chunk:
    def __init__(self, uid: str, text: str, chunk_id: int = 1):
        self.chunk_uid = uid
        self.id = chunk_id
        self.keyword_text = text
        self.content = text


def test_dominant_identifier_detects_matter_code():
    assert _dominant_identifier_in_query("YZ0000000QR13010003") == "YZ0000000QR13010003"
    assert _dominant_identifier_in_query("新生儿医保") is None


def test_layered_score_matter_code_meets_hybrid_floor():
    query = "YZ0000000QR13010003"
    text = "事项编号：YZ0000000QR13010003；事项名称：测试事项"
    from app.services.retrieval_service import _extract_query_term_layers

    layers = _extract_query_term_layers(query)
    score = _layered_keyword_match_score(text, layers)
    assert score >= _min_keyword_hybrid_score_for_query(query)


def test_filter_hybrid_keyword_keeps_identifier_hit():
    query = "YZ0000000QR13010003"
    text = "事项编号：YZ0000000QR13010003"
    candidates = [
        {
            "chunk": _Chunk("a", text),
            "document_name": "事项清单",
            "keyword_score": 0.0,
        }
    ]
    rescored = _rescore_keyword_candidates(candidates, query=query, limit=5)
    filtered = _filter_hybrid_channel_candidates(
        rescored,
        score_key="keyword_score",
        score_threshold=None,
        channel="keyword",
        query=query,
    )
    assert len(filtered) == 1
    assert filtered[0]["keyword_score"] >= 4.0


def test_filter_hybrid_vector_keeps_chunk_with_exact_code():
    query = "YZ0000000QR13010003"
    text = "事项编号：YZ0000000QR13010003"
    candidates = [
        {
            "chunk": _Chunk("a", text),
            "document_name": "事项清单",
            "vector_score": 0.42,
        }
        for _ in range(12)
    ]
    candidates.append(
        {
            "chunk": _Chunk("target", text),
            "document_name": "事项清单",
            "vector_score": 0.41,
        }
    )
    filtered = _filter_hybrid_channel_candidates(
        candidates,
        score_key="vector_score",
        score_threshold=None,
        channel="vector",
        query=query,
    )
    uids = {item["chunk"].chunk_uid for item in filtered}
    assert "target" in uids


def test_hybrid_cross_domain_guard_allows_identifier_keyword():
    query = "YZ0000000QR13010003"
    keyword_candidates = [{"keyword_score": 4.0, "chunk": object()}]
    merged = {"u1": {"vector_score": None, "keyword_score": 4.0}}
    assert _hybrid_cross_domain_guard(
        keyword_candidates=keyword_candidates,
        vector_candidates=[],
        merged=merged,
        query=query,
    )
