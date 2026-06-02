import hashlib
from unittest.mock import MagicMock

import pytest

from app.core.errors import AppError
from app.models.knowledge_base import KnowledgeDocumentStatus
from app.services import knowledge_document_service as svc


def test_upload_skips_duplicate_when_requested():
    kb = MagicMock()
    kb.default_chunk_size = 512
    kb.default_chunk_overlap = 50
    existing = MagicMock()
    existing.status = KnowledgeDocumentStatus.INDEXED.value
    existing.id = 42

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.side_effect = [kb, existing]

    result = svc.upload_document(
        db,
        space_id=1,
        kb_id=1,
        file_name="docs/a.txt",
        file_bytes=b"hello",
        mime_type="text/plain",
        chunk_size=None,
        chunk_overlap=None,
        skip_if_duplicate=True,
    )

    assert result["upload_skipped"] is True
    assert result["skip_reason"] == "duplicate_content"
    assert result["id"] == 42
    db.add.assert_not_called()


def test_upload_raises_on_duplicate_by_default():
    kb = MagicMock()
    kb.default_chunk_size = 512
    kb.default_chunk_overlap = 50
    existing = MagicMock()
    existing.status = KnowledgeDocumentStatus.INDEXED.value

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.side_effect = [kb, existing]

    with pytest.raises(AppError) as exc:
        svc.upload_document(
            db,
            space_id=1,
            kb_id=1,
            file_name="docs/a.txt",
            file_bytes=b"hello",
            mime_type="text/plain",
            chunk_size=None,
            chunk_overlap=None,
            skip_if_duplicate=False,
        )

    assert exc.value.code == "DOCUMENT_ALREADY_EXISTS"
