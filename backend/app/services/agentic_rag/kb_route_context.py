from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.knowledge_base import KnowledgeBase, KnowledgeDocument
from app.services.knowledge_base_service import get_knowledge_base_stats

_KB_TYPE_LABEL = {
    "classic": "向量知识库",
    "lightrag": "图知识库",
}

_GENERATE_KB_BINDING_INSTRUCTION = (
    "当前对话已绑定以下知识库（本轮可能未检索文档内容）。"
    "若用户询问绑定了哪些知识库、知识范围或检索能力，请依据下列信息如实回答，"
    "不要声称未绑定或未选择任何知识库。"
)


def format_kb_binding_for_generate(kb_context: str) -> str:
    """Format bound-KB metadata for the final answer LLM when retrieval was skipped."""
    text = (kb_context or "").strip()
    if not text:
        return ""
    return f"{_GENERATE_KB_BINDING_INSTRUCTION}\n\n已绑定知识库：\n{text}"


def build_kb_route_context(
    db: Session,
    *,
    enterprise_space_id: int,
    knowledge_base_ids: list[int],
    doc_titles_per_kb: int | None = None,
    max_chars: int | None = None,
) -> str:
    """Aggregate KB metadata for Agentic route LLM (no vector search)."""
    settings = get_settings()
    per_kb = doc_titles_per_kb if doc_titles_per_kb is not None else settings.agentic_route_doc_titles_per_kb
    char_limit = max_chars if max_chars is not None else settings.agentic_route_kb_context_max_chars

    ordered_ids: list[int] = []
    for kid in knowledge_base_ids:
        if kid not in ordered_ids:
            ordered_ids.append(int(kid))
    if not ordered_ids:
        return ""

    rows = db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.enterprise_space_id == enterprise_space_id,
            KnowledgeBase.id.in_(ordered_ids),
            KnowledgeBase.status != "deleted",
        )
    ).scalars().all()
    kb_by_id = {kb.id: kb for kb in rows}

    blocks: list[str] = []
    for kb_id in ordered_ids:
        kb = kb_by_id.get(kb_id)
        if kb is None:
            continue
        stats = get_knowledge_base_stats(db, knowledge_base=kb)
        type_label = _KB_TYPE_LABEL.get(str(kb.kb_type or "classic"), str(kb.kb_type or "classic"))
        desc = (kb.description or "").strip() or "（无描述）"
        doc_titles = _indexed_document_titles(db, knowledge_base_id=kb.id, limit=max(1, per_kb))
        title_lines = "\n".join(f"  - {name}" for name in doc_titles) if doc_titles else "  - （暂无已索引文档）"
        blocks.append(
            "\n".join(
                [
                    f"【{kb.name}】（{type_label}）",
                    f"描述：{desc}",
                    (
                        f"统计：文档 {stats['document_total']} 篇，"
                        f"已索引 {stats['indexed_document_total']} 篇，"
                        f"片段 {stats['chunk_total']} 条"
                    ),
                    "部分文档标题：",
                    title_lines,
                ]
            )
        )

    if not blocks:
        return ""

    header = f"共 {len(blocks)} 个知识库：\n"
    text = header + "\n\n".join(blocks)
    if len(text) <= char_limit:
        return text

    trimmed_blocks: list[str] = []
    budget = char_limit - len(header) - 20
    for block in blocks:
        if budget <= 0:
            trimmed_blocks.append("…（更多知识库已省略）")
            break
        if len(block) <= budget:
            trimmed_blocks.append(block)
            budget -= len(block) + 2
        else:
            trimmed_blocks.append(block[: max(0, budget - 1)] + "…")
            break
    return header + "\n\n".join(trimmed_blocks)


def _indexed_document_titles(db: Session, *, knowledge_base_id: int, limit: int) -> list[str]:
    rows = db.execute(
        select(KnowledgeDocument.document_name)
        .where(
            KnowledgeDocument.knowledge_base_id == knowledge_base_id,
            KnowledgeDocument.status.in_(("indexed", "graph_indexed")),
        )
        .order_by(KnowledgeDocument.updated_at.desc())
        .limit(limit)
    ).all()
    return [str(row[0]).strip() for row in rows if row and str(row[0]).strip()]
