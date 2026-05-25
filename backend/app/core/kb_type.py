from __future__ import annotations

from app.core.errors import AppError
from app.models.knowledge_base import KnowledgeBase

KB_TYPE_CLASSIC = "classic"
KB_TYPE_LIGHTRAG = "lightrag"


def get_kb_type(knowledge_base: KnowledgeBase) -> str:
    raw = getattr(knowledge_base, "kb_type", None)
    if raw in (KB_TYPE_CLASSIC, KB_TYPE_LIGHTRAG):
        return str(raw)
    config = knowledge_base.config if isinstance(knowledge_base.config, dict) else {}
    legacy = config.get("kb_type")
    if legacy in (KB_TYPE_CLASSIC, KB_TYPE_LIGHTRAG):
        return str(legacy)
    return KB_TYPE_CLASSIC


def build_lightrag_workspace(space_id: int, kb_id: int) -> str:
    return f"space_{space_id}_kb_{kb_id}"


def sanitize_workspace_label(workspace: str) -> str:
    """Align with LightRAG Neo4JStorage._get_workspace_label (backtick-safe)."""
    value = (workspace or "").strip()
    if not value:
        return "base"
    return value.replace("`", "``")


def ensure_lightrag_kb(knowledge_base: KnowledgeBase) -> None:
    if get_kb_type(knowledge_base) != KB_TYPE_LIGHTRAG:
        raise AppError(
            status_code=400,
            code="KB_TYPE_NOT_LIGHTRAG",
            message="仅图知识库（kb_type=lightrag）支持此操作",
        )


def is_lightrag_kb(knowledge_base: KnowledgeBase) -> bool:
    return get_kb_type(knowledge_base) == KB_TYPE_LIGHTRAG
