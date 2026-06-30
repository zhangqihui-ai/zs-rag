from app.services.chat_service import extract_citation_refs_from_text, filter_citations_by_answer


def test_extract_citation_refs_from_text() -> None:
    assert extract_citation_refs_from_text("依据[1]与[2]说明") == [1, 2]
    assert extract_citation_refs_from_text("重复[1]再[1]") == [1]
    assert extract_citation_refs_from_text("全角［3］") == [3]
    assert extract_citation_refs_from_text("根据片段 ① ② 说明") == [1, 2]
    assert extract_citation_refs_from_text("见①与[2]") == [1, 2]
    assert extract_citation_refs_from_text("无引文") == []


def test_filter_citations_by_answer() -> None:
    citations = [
        {"ref": 1, "document_name": "刑法 A"},
        {"ref": 2, "document_name": "刑法 B"},
    ]
    filtered, count = filter_citations_by_answer(citations, "结论[1]成立。")
    assert count == 1
    assert len(filtered) == 1
    assert filtered[0]["ref"] == 1


def test_filter_citations_by_answer_circled_refs() -> None:
    citations = [
        {"ref": 1, "document_name": "刑法 A"},
        {"ref": 2, "document_name": "刑法 B"},
    ]
    filtered, count = filter_citations_by_answer(citations, "根据片段 ① ②：结论成立。")
    assert count == 2
    assert [item["ref"] for item in filtered] == [1, 2]


def test_filter_citations_by_answer_without_refs() -> None:
    citations = [{"ref": 1, "document_name": "刑法 A"}]
    filtered, count = filter_citations_by_answer(citations, "未标注引文。")
    assert count == 0
    assert filtered == []
