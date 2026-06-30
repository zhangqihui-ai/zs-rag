"""知识库检索默认配置（新建库与缺省回退共用）。"""

from __future__ import annotations

from typing import Any

# 混合检索：向量 0.3 / 关键词 0.7，偏精确词面命中（中文制度、法条类语料）
DEFAULT_VECTOR_WEIGHT = 0.3
DEFAULT_SCORE_THRESHOLD = 0.5
DEFAULT_RETRIEVAL_MODE = "hybrid"
DEFAULT_TOP_K = 5
DEFAULT_VECTOR_RETRIEVAL_TOP_K = 8
DEFAULT_LIGHTRAG_RETRIEVAL_TOP_K = 8
DEFAULT_MERGE_TOP_K = DEFAULT_TOP_K
DEFAULT_INCLUDE_IMAGE_OCR = False
DEFAULT_IMAGE_OCR_SCORE_FACTOR = 0.55
DEFAULT_AUTO_IMAGE_OCR_ON_UI_QUERY = True
# 混合检索通道融合方式：weighted=归一化加权求和（默认）；rrf=加权倒数排名融合
DEFAULT_FUSION_METHOD = "weighted"
# RRF 平滑常数，业界惯例 60，越大越拉平头部优势
DEFAULT_RRF_K = 60


def default_retrieval_config_patch() -> dict[str, Any]:
    """写入 knowledge_base.config.retrieval 的默认片段。"""
    return {
        "vector_weight": DEFAULT_VECTOR_WEIGHT,
        "hybrid_strategy": "weight",
        "fusion_method": DEFAULT_FUSION_METHOD,
        "score_threshold_enabled": True,
        "include_image_ocr": DEFAULT_INCLUDE_IMAGE_OCR,
        "image_ocr_score_factor": DEFAULT_IMAGE_OCR_SCORE_FACTOR,
        "auto_image_ocr_on_ui_query": DEFAULT_AUTO_IMAGE_OCR_ON_UI_QUERY,
    }


def apply_retrieval_defaults_to_payload(data: dict[str, Any]) -> dict[str, Any]:
    """创建知识库时补齐检索相关缺省字段。"""
    out = dict(data)
    if out.get("default_retrieval_mode") is None:
        out["default_retrieval_mode"] = DEFAULT_RETRIEVAL_MODE
    if out.get("default_top_k") is None:
        out["default_top_k"] = DEFAULT_TOP_K
    if out.get("default_score_threshold") is None:
        out["default_score_threshold"] = DEFAULT_SCORE_THRESHOLD

    config = dict(out.get("config") or {})
    retrieval = dict(config.get("retrieval") or {})
    for key, value in default_retrieval_config_patch().items():
        retrieval.setdefault(key, value)
    config["retrieval"] = retrieval
    out["config"] = config
    return out
