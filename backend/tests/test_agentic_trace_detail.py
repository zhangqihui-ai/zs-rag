from app.services.agentic_rag.nodes import _trace_candidate_summaries, _trace_grade_summaries


def test_trace_candidate_summaries() -> None:
    rows = _trace_candidate_summaries(
        [
            {
                "document_name": "刑法",
                "content": "正当防卫不负刑事责任。",
                "score": 0.8123,
                "chunk_index": 11,
                "citation": {"page_no": 7},
            }
        ]
    )
    assert len(rows) == 1
    assert rows[0]["document_name"] == "刑法"
    assert rows[0]["page_no"] == 7
    assert rows[0]["chunk_index"] == 11
    assert "正当防卫" in rows[0]["preview"]


def test_trace_grade_summaries() -> None:
    rows = _trace_grade_summaries(
        [
            {
                "document_name": "刑法",
                "score": 0.81,
                "knowledge_base_id": 3,
                "document_id": 12,
                "chunk_id": 456,
                "chunk_index": 2,
                "content": "正当防卫不负刑事责任。",
                "metadata": {"source": "vector"},
                "citation": {"page_no": 7},
                "agentic_grade": {
                    "relevant": False,
                    "score": 0,
                    "reason": "片段讨论正当防卫构成要件，与量刑问题关联不足",
                },
            }
        ]
    )
    assert len(rows) == 1
    assert rows[0]["relevant"] is False
    assert rows[0]["grade_score"] == 0
    assert "正当防卫" in rows[0]["reason"]
    assert rows[0]["knowledge_base_id"] == 3
    assert rows[0]["chunk_id"] == 456
    assert rows[0]["page_no"] == 7
    assert "正当防卫" in rows[0]["preview"]
    assert "正当防卫" in rows[0]["content"]
