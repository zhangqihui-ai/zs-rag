#!/usr/bin/env python3
"""将库中已 INDEXED 文档的切片全量写入 OpenSearch（需环境变量 OPENSEARCH_URL）。

用法（在 backend 目录或设置 PYTHONPATH）:
  export OPENSEARCH_URL=http://localhost:9200
  cd backend && python scripts/reindex_opensearch_chunks.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.knowledge_base import (  # noqa: E402
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
)
from app.services import opensearch_chunk_service  # noqa: E402


def main() -> None:
    if not opensearch_chunk_service.is_enabled():
        print("OPENSEARCH_URL 未配置，跳过。", file=sys.stderr)
        sys.exit(1)

    batch_docs: list[tuple[int, str]] = []

    with SessionLocal() as db:
        rows = db.execute(
            select(KnowledgeDocument.id, KnowledgeDocument.document_name)
            .where(KnowledgeDocument.status == KnowledgeDocumentStatus.INDEXED.value)
            .order_by(KnowledgeDocument.id)
        ).all()
        batch_docs = [(int(r[0]), str(r[1])) for r in rows]

    total = len(batch_docs)
    print(f"待同步文档数: {total}", flush=True)
    t0 = time.time()
    ok = 0

    with SessionLocal() as db:
        for i, (doc_id, doc_name) in enumerate(batch_docs, 1):
            chunks = list(
                db.execute(
                    select(KnowledgeChunk)
                    .where(KnowledgeChunk.document_id == doc_id)
                    .order_by(KnowledgeChunk.chunk_index)
                ).scalars().all()
            )
            if not chunks:
                continue
            try:
                opensearch_chunk_service.bulk_upsert_chunks(document_name=doc_name, chunks=chunks)
                ok += 1
            except Exception as exc:
                print(f"doc_id={doc_id} 失败: {exc}", file=sys.stderr)
            if i % 50 == 0 or i == total:
                print(f"进度 {i}/{total} 成功写入 {ok} … {round(time.time() - t0, 1)}s", flush=True)

    print(f"完成：成功 {ok}/{total}，耗时 {round(time.time() - t0, 1)}s", flush=True)


if __name__ == "__main__":
    main()
