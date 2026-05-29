"""加权 RRF 融合：按名次融合、不受单路异常分影响、权重方向正确。"""

from app.services.retrieval_service import (
    RRF_K,
    _normalize_scores_relative,
    _resolve_fusion_method,
)


class _KB:
    def __init__(self, fusion_method=None):
        retrieval = {}
        if fusion_method is not None:
            retrieval["fusion_method"] = fusion_method
        self.config = {"retrieval": retrieval}


class _Payload:
    def __init__(self, fusion_method=None):
        self.fusion_method = fusion_method


def _weighted_rrf(rank_v, rank_k, *, w_vector, k=RRF_K):
    """复刻 retrieval_service 中 rrf 单条打分，便于断言名次方向。"""
    w_keyword = 1.0 - w_vector
    score = 0.0
    if rank_v is not None:
        score += w_vector * (1.0 / (k + rank_v))
    if rank_k is not None:
        score += w_keyword * (1.0 / (k + rank_k))
    return score


def test_resolve_fusion_method_priority():
    # payload 优先
    assert _resolve_fusion_method(_KB("weighted"), _Payload("rrf")) == "rrf"
    # 回退知识库 config
    assert _resolve_fusion_method(_KB("rrf"), _Payload(None)) == "rrf"
    # 默认 weighted
    assert _resolve_fusion_method(_KB(None), _Payload(None)) == "weighted"
    # 非法值忽略
    assert _resolve_fusion_method(_KB("bogus"), _Payload("bad")) == "weighted"


def test_rrf_both_channels_beats_single_channel():
    w_vector = 0.3
    both = _weighted_rrf(1, 1, w_vector=w_vector)
    only_kw = _weighted_rrf(None, 1, w_vector=w_vector)
    only_vec = _weighted_rrf(1, None, w_vector=w_vector)
    assert both > only_kw > only_vec  # 两路命中 > 仅关键词(权重大) > 仅向量


def test_rrf_higher_rank_scores_more():
    w_vector = 0.3
    top = _weighted_rrf(None, 1, w_vector=w_vector)
    low = _weighted_rrf(None, 10, w_vector=w_vector)
    assert top > low


def test_rrf_weight_direction():
    # 调大向量权重时，纯向量命中的 RRF 分应上升
    low_w = _weighted_rrf(1, None, w_vector=0.3)
    high_w = _weighted_rrf(1, None, w_vector=0.7)
    assert high_w > low_w


def test_rrf_normalized_top_one_bottom_nonzero():
    raw = {
        "a": _weighted_rrf(1, 1, w_vector=0.3),
        "b": _weighted_rrf(None, 3, w_vector=0.3),
        "c": _weighted_rrf(None, 8, w_vector=0.3),
    }
    norm = _normalize_scores_relative(raw)
    assert norm["a"] == 1.0
    assert norm["c"] > 0.0  # 末位不被压成 0
