from app.services.lightrag_engine import (
    LIGHTRAG_PRECHUNK_BOUNDARY,
    _parse_lightrag_chunk_extract_line,
    _pipeline_message_targets_doc,
    build_lightrag_prechunked_text,
    resolve_lightrag_entity_extract_max_gleaning,
    resolve_lightrag_entity_types,
    resolve_lightrag_index_chunk_mode,
    resolve_lightrag_prechunk_insert_settings,
    resolve_lightrag_split_by_character_only,
    should_use_lightrag_prechunks,
)


def test_build_lightrag_prechunked_text_roundtrip() -> None:
    chunks = ["事项A", "事项B", "事项C"]
    joined = build_lightrag_prechunked_text(chunks)
    assert joined.split(LIGHTRAG_PRECHUNK_BOUNDARY) == chunks


def test_should_use_lightrag_prechunks_small_doc() -> None:
    chunks = ["a", "b", "c"]
    assert should_use_lightrag_prechunks("x" * 5000, chunks) is False


def test_should_use_lightrag_prechunks_large_doc() -> None:
    chunks = ["row"] * 100
    assert should_use_lightrag_prechunks("x" * 200_000, chunks) is True


def test_should_use_lightrag_prechunks_empty_chunks() -> None:
    assert should_use_lightrag_prechunks("x" * 500_000, []) is False


def test_should_use_lightrag_prechunks_reuse_parse_mode() -> None:
    chunks = ["row"] * 3
    assert should_use_lightrag_prechunks("short", chunks, index_chunk_mode="reuse_parse") is True


def test_should_use_lightrag_prechunks_native_mode() -> None:
    chunks = ["row"] * 100
    assert should_use_lightrag_prechunks("x" * 500_000, chunks, index_chunk_mode="native") is False


def test_should_use_lightrag_prechunks_custom_threshold() -> None:
    chunks = ["a"]
    assert should_use_lightrag_prechunks("x" * 1000, chunks, prechunk_min_chars=500) is True
    assert should_use_lightrag_prechunks("x" * 100, chunks, prechunk_min_chars=500) is False


def test_resolve_lightrag_index_chunk_mode() -> None:
    assert resolve_lightrag_index_chunk_mode({}) == "auto"
    assert resolve_lightrag_index_chunk_mode({"index_chunk_mode": "reuse_parse"}) == "reuse_parse"
    assert resolve_lightrag_index_chunk_mode({"index_chunk_mode": "invalid"}) == "auto"


def test_resolve_lightrag_entity_types() -> None:
    assert resolve_lightrag_entity_types({}) is None
    assert resolve_lightrag_entity_types({"entity_types": ["Person", ""]}) == ["Person"]
    assert resolve_lightrag_entity_types({"entity_types": []}) is None


def test_resolve_lightrag_entity_extract_max_gleaning() -> None:
    assert resolve_lightrag_entity_extract_max_gleaning({}) is None
    assert resolve_lightrag_entity_extract_max_gleaning({"entity_extract_max_gleaning": 0}) == 0
    assert resolve_lightrag_entity_extract_max_gleaning({"entity_extract_max_gleaning": 1}) == 1


def test_resolve_lightrag_split_by_character_only() -> None:
    assert resolve_lightrag_split_by_character_only({}) is False
    assert resolve_lightrag_split_by_character_only({"split_by_character_only": True}) is True


def test_resolve_lightrag_prechunk_insert_settings_defaults() -> None:
    split_only, token_size = resolve_lightrag_prechunk_insert_settings(
        {},
        ["短段"],
        base_chunk_token_size=4096,
    )
    assert split_only is True
    assert token_size >= 4096


def test_resolve_lightrag_prechunk_insert_settings_respects_explicit_false() -> None:
    split_only, token_size = resolve_lightrag_prechunk_insert_settings(
        {"split_by_character_only": False},
        ["短段"],
        base_chunk_token_size=4096,
    )
    assert split_only is False
    assert token_size == 4096


def test_resolve_lightrag_prechunk_insert_settings_kb_override() -> None:
    split_only, token_size = resolve_lightrag_prechunk_insert_settings(
        {"chunk_token_size": 8192},
        ["短段"],
        base_chunk_token_size=4096,
    )
    assert split_only is True
    assert token_size == 8192


def test_oversized_prechunk_subsplit_when_not_character_only() -> None:
    from lightrag.operate import chunking_by_token_size

    from app.core.offline_tokenizer import build_offline_tokenizer

    tokenizer = build_offline_tokenizer()
    small = "短段" * 10
    big = "事项名称：" + ("字段值|" * 3000)
    content = build_lightrag_prechunked_text([small, big, small])
    chunks = chunking_by_token_size(
        tokenizer,
        content,
        split_by_character=LIGHTRAG_PRECHUNK_BOUNDARY,
        split_by_character_only=False,
        chunk_overlap_token_size=50,
        chunk_token_size=4096,
    )
    assert len(chunks) >= 4
    assert all(int(item["tokens"]) <= 4096 for item in chunks)


def test_parse_lightrag_chunk_extract_line() -> None:
    parsed = _parse_lightrag_chunk_extract_line(
        "Chunk 4 of 8 extracted 12 Ent + 9 Rel chunk-abc123"
    )
    assert parsed == (4, 8, 12, 9)


def test_pipeline_chunk_message_matches_doc_chunk_key() -> None:
    chunk_key = "chunk-abc123"
    msg = f"Chunk 2 of 8 extracted 1 Ent + 2 Rel {chunk_key}"
    assert _pipeline_message_targets_doc(
        msg,
        doc_id="doc-1953",
        file_name="demo.xlsx",
        active_pipeline_doc=None,
        doc_chunk_keys={chunk_key},
    )
