"""P0：强锚点分层 + 模板词降权 + 锚点必达重打分。"""

from app.services.retrieval_service import (
    _extract_query_term_layers,
    _layered_keyword_match_score,
    _rescore_keyword_candidates,
)


class _Chunk:
    def __init__(self, uid: str, text: str, chunk_id: int = 1):
        self.chunk_uid = uid
        self.id = chunk_id
        self.keyword_text = text
        self.content = text


def test_extract_layers_newborn_medical_insurance():
    layers = _extract_query_term_layers("新生儿医保如何办理")
    assert "新生儿医保" in layers.anchors
    assert "新生儿" in layers.anchors
    assert "医保" in layers.anchors
    assert "如何" not in layers.anchors
    assert "办理" not in layers.anchors
    assert layers.specific_anchors == ("新生儿医保",)


def test_extract_layers_two_char_only_query():
    layers = _extract_query_term_layers("落户怎么办")
    assert layers.anchors == ("落户",)
    assert layers.specific_anchors == ("落户",)


def test_layered_score_rejects_policy_noise():
    layers = _extract_query_term_layers("新生儿医保如何办理")
    policy = (
        "第八条通过优化医保基金结算清单上传、智能审核等流程，压缩费用对账、申报受理、"
        "基金拨付等工作时限，提高即时结算效率。"
    )
    assert _layered_keyword_match_score(policy, layers) == 0.0


def test_layered_score_accepts_newborn_content():
    layers = _extract_query_term_layers("新生儿医保如何办理")
    guide = "城乡居民参保登记（新生儿）需在出生后办理医保参保手续。"
    score = _layered_keyword_match_score(guide, layers)
    assert score >= 3.0


def test_layered_score_single_domain_word_query():
    layers = _extract_query_term_layers("医保政策")
    text = "基本医保基金即时结算经办规程"
    score = _layered_keyword_match_score(text, layers)
    assert score >= 1.5

def test_layered_score_justifiable_defense():
    layers = _extract_query_term_layers("正当防卫怎么判刑")
    text = "正当防卫超过必要限度造成重大损害的，应当负刑事责任。"
    score = _layered_keyword_match_score(text, layers)
    assert score >= 2.5


def test_rescore_keyword_candidates_filters_noise():
    layers = _extract_query_term_layers("新生儿医保如何办理")
    policy = (
        "第八条通过优化医保基金结算清单上传、智能审核等流程，压缩费用对账、申报受理、"
        "基金拨付等工作时限，提高即时结算效率。"
    )
    guide = "新生儿医保参保登记办理流程说明"
    candidates = [
        {"chunk": _Chunk("a", policy), "document_name": "policy", "keyword_score": 0.0},
        {"chunk": _Chunk("b", guide), "document_name": "guide", "keyword_score": 0.0},
    ]
    out = _rescore_keyword_candidates(candidates, query="新生儿医保如何办理", limit=5)
    assert len(out) == 1
    assert out[0]["chunk"].chunk_uid == "b"
    assert _layered_keyword_match_score(policy, layers) == 0.0
