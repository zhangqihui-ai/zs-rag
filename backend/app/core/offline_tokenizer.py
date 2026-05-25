"""Offline-safe tokenizer for LightRAG text chunking (no Azure/tiktoken download)."""

from __future__ import annotations

from lightrag.utils import Tokenizer


class _CharLevelEncoding:
    """Character-level pseudo encoding for chunking without network."""

    def encode(self, content: str) -> list[int]:
        return [ord(c) for c in content]

    def decode(self, tokens: list[int]) -> str:
        return "".join(chr(t) for t in tokens)


def build_offline_tokenizer() -> Tokenizer:
    """Build a LightRAG Tokenizer that never contacts openaipublic.blob.core.windows.net."""
    return Tokenizer(model_name="offline-char", tokenizer=_CharLevelEncoding())
