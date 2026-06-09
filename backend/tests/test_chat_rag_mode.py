from app.schemas.chat import ChatConfigurationUpdate
from app.services.chat_service import (
    _clamp_agentic_max_iterations,
    _clamp_agentic_min_relevant_docs,
    _normalize_rag_mode,
)


def test_normalize_rag_mode() -> None:
    assert _normalize_rag_mode("classic") == "classic"
    assert _normalize_rag_mode("agentic") == "agentic"
    assert _normalize_rag_mode("unknown") == "classic"
    assert _normalize_rag_mode(None) == "classic"


def test_clamp_agentic_settings() -> None:
    assert 1 <= _clamp_agentic_max_iterations(99) <= 5
    assert 1 <= _clamp_agentic_min_relevant_docs(99) <= 10


def test_configuration_update_excludes_rag_mode_only() -> None:
    fields = ChatConfigurationUpdate.model_fields
    assert "rag_mode" in fields
    assert fields["rag_mode"].exclude is True
    assert fields["agentic_max_iterations"].exclude is not True
    assert fields["agentic_min_relevant_docs"].exclude is not True
