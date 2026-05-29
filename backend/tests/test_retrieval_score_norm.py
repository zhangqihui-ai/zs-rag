"""混合检索分数归一化：max 归一化不应把批次最弱命中压成 0。"""

from app.services.retrieval_service import (
    _normalize_scores,
    _normalize_scores_relative,
)


def test_min_max_zeros_the_bottom():
    """对照：旧的 min-max 会把最小值压成 0（这正是要规避的行为）。"""
    out = _normalize_scores({"a": 5.45, "b": 5.0, "c": 4.0})
    assert out["a"] == 1.0
    assert out["c"] == 0.0


def test_relative_keeps_bottom_nonzero():
    out = _normalize_scores_relative({"a": 5.45, "b": 5.0, "c": 4.0})
    assert out["a"] == 1.0
    assert out["c"] > 0.0
    assert out["c"] == 4.0 / 5.45


def test_relative_flat_returns_one_when_above_floor():
    out = _normalize_scores_relative({"a": 5.0, "b": 5.0}, zero_if_flat_below=3.0)
    assert out == {"a": 1.0, "b": 1.0}


def test_relative_flat_zeroed_below_floor():
    out = _normalize_scores_relative({"a": 1.0, "b": 1.0}, zero_if_flat_below=3.0)
    assert out == {"a": 0.0, "b": 0.0}


def test_relative_empty_and_nonpositive():
    assert _normalize_scores_relative({}) == {}
    assert _normalize_scores_relative({"a": 0.0, "b": 0.0}) == {"a": 0.0, "b": 0.0}
