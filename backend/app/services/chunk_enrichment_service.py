"""入库 LLM 增强：为 chunk 生成 keywords / 假设问题，写入 keyword_text 与 metadata。"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.core.parser_config import EnrichmentOptions
from app.core.provider_adapter import get_provider
from app.core.text_chunker import ChunkCandidate
from app.models.knowledge_base import KnowledgeBase
from app.models.model_management import AIModel, AIModelDefault


def _extract_llm_text(result_data: object) -> str:
    if not isinstance(result_data, dict):
        return str(result_data or "")
    choices = result_data.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        content = message.get("content")
        if content:
            return str(content)
    return str(result_data)

logger = logging.getLogger(__name__)

_LLM_INPUT_MAX_CHARS = 2000


@dataclass
class ChunkEnrichmentResult:
    keywords: list[str]
    questions: list[str]
    keyword_text: str


def _resolve_enrichment_llm(db: Session, *, knowledge_base: KnowledgeBase, llm_id: int | None) -> AIModel:
    if llm_id is not None:
        model = db.execute(
            select(AIModel)
            .options(selectinload(AIModel.provider))
            .where(
                AIModel.id == int(llm_id),
                AIModel.enterprise_space_id == knowledge_base.enterprise_space_id,
            )
        ).scalar_one_or_none()
        if model is None:
            raise AppError(status_code=404, code="MODEL_NOT_FOUND", message="入库增强 LLM 不存在")
        if not model.is_enabled:
            raise AppError(status_code=400, code="MODEL_DISABLED", message="入库增强 LLM 未启用")
        if model.model_type != "llm":
            raise AppError(status_code=400, code="MODEL_TYPE_MISMATCH", message="enrichment.llm_id 须为 LLM 模型")
        return model

    binding = db.execute(
        select(AIModelDefault)
        .options(selectinload(AIModelDefault.model).selectinload(AIModel.provider))
        .where(
            AIModelDefault.enterprise_space_id == knowledge_base.enterprise_space_id,
            AIModelDefault.model_type == "llm",
        )
    ).scalar_one_or_none()
    if binding is None or binding.model is None:
        raise AppError(status_code=400, code="LLM_NOT_CONFIGURED", message="企业空间未配置默认 LLM，无法启用入库增强")
    model = binding.model
    if not model.is_enabled:
        raise AppError(status_code=400, code="MODEL_DISABLED", message="默认 LLM 未启用")
    return model


def _parse_enrichment_json(raw: str) -> tuple[list[str], list[str]]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [], []
    if not isinstance(data, dict):
        return [], []
    keywords_raw = data.get("keywords") or []
    questions_raw = data.get("questions") or []
    keywords = [str(k).strip() for k in keywords_raw if str(k).strip()] if isinstance(keywords_raw, list) else []
    questions = [str(q).strip() for q in questions_raw if str(q).strip()] if isinstance(questions_raw, list) else []
    return keywords[:12], questions[:5]


def build_keyword_text(
    content: str,
    *,
    keywords: list[str],
    questions: list[str],
) -> str:
    parts = [content.strip()]
    if keywords:
        parts.append("关键词：" + "；".join(keywords))
    if questions:
        parts.append("问题：" + "；".join(questions))
    return "\n".join(p for p in parts if p)


def enrich_chunk_with_llm(
    *,
    content: str,
    heading_path: str | None,
    model: AIModel,
    options: EnrichmentOptions,
) -> ChunkEnrichmentResult | None:
    snippet = content.strip()
    if len(snippet) > _LLM_INPUT_MAX_CHARS:
        snippet = snippet[:_LLM_INPUT_MAX_CHARS] + "…"
    if not snippet:
        return None

    tasks: list[str] = []
    if options.generate_keywords:
        tasks.append("3-8 个检索关键词或短语（keywords）")
    if options.generate_questions:
        tasks.append(f"1-{options.max_questions} 个用户可能提出的假设问题（questions）")
    if not tasks:
        return None

    context = f"章节路径：{heading_path}\n\n" if heading_path else ""
    prompt = (
        "你是知识库索引助手。根据以下文档片段，生成便于检索的 JSON，仅输出 JSON，不要 markdown 代码块。\n"
        f"需要生成：{'、'.join(tasks)}。\n"
        '格式：{"keywords": ["..."], "questions": ["..."]}\n\n'
        f"{context}{snippet}"
    )

    provider = get_provider(model.provider)
    response = provider.chat(model.model_name, [{"role": "user", "content": prompt}], timeout=60.0)
    if not response.success:
        logger.warning("chunk enrichment LLM failed: %s", response.message)
        return None
    raw = _extract_llm_text(response.data)
    keywords, questions = _parse_enrichment_json(raw)
    if options.generate_questions:
        questions = questions[: options.max_questions]
    if not keywords and not questions:
        return None
    keyword_text = build_keyword_text(content, keywords=keywords, questions=questions)
    return ChunkEnrichmentResult(keywords=keywords, questions=questions, keyword_text=keyword_text)


def enrich_chunk_candidates(
    db: Session,
    *,
    knowledge_base: KnowledgeBase,
    candidates: list[ChunkCandidate],
    options: EnrichmentOptions,
    emit: Callable[[str], None] | None = None,
) -> None:
    """就地更新 ChunkCandidate.metadata 与 enrichment_keyword_text。"""
    if not options.enabled:
        return

    model = _resolve_enrichment_llm(db, knowledge_base=knowledge_base, llm_id=options.llm_id)
    db.commit()

    total = len(candidates)
    if emit:
        emit(f"入库增强已启用，共 {total} 个块，LLM={model.model_name}…")

    for i, candidate in enumerate(candidates, start=1):
        meta = dict(candidate.metadata or {})
        try:
            result = enrich_chunk_with_llm(
                content=candidate.content,
                heading_path=candidate.heading_path,
                model=model,
                options=options,
            )
        except Exception as exc:
            logger.warning("chunk enrichment error idx=%s: %s", i, exc)
            result = None
        if result:
            meta["enrichment_keywords"] = result.keywords
            meta["enrichment_questions"] = result.questions
            candidate.metadata = meta
            candidate.enrichment_keyword_text = result.keyword_text
        if emit and (i <= 3 or i == total or i % 50 == 0):
            emit(f"入库增强进度 {i}/{total}…")
