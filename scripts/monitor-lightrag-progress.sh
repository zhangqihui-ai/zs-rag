#!/usr/bin/env bash
# Monitor LightRAG graph indexing progress for a document (docker compose local).
set -euo pipefail

KB_ID="${KB_ID:-41}"
DOC_ID="${DOC_ID:-1955}"
# Task restart time for "new since restart" (UTC); override if re-parsed again.
TASK_START_UTC="${TASK_START_UTC:-2026-06-08T09:13:26+00:00}"

docker exec -i zs-rag-backend python3 - <<PY
import json, time
from datetime import datetime, timezone
from app.db.session import SessionLocal
from app.models.knowledge_base import KnowledgeBase, KnowledgeDocument
from app.services.lightrag_engine import (
    _lightrag_doc_status,
    _count_lightrag_extracted_chunks,
    _lightrag_llm_cache_path,
)

kb_id, doc_id = ${KB_ID}, ${DOC_ID}
task_start = datetime.fromisoformat("${TASK_START_UTC}")
db = SessionLocal()
kb = db.get(KnowledgeBase, kb_id)
doc = db.get(KnowledgeDocument, doc_id)
if not kb or not doc:
    print(f"ERROR: kb={kb_id} doc={doc_id} not found")
    raise SystemExit(1)

status, entry = _lightrag_doc_status(kb, doc)
chunks = [str(x) for x in (entry or {}).get("chunks_list") or []]
done = _count_lightrag_extracted_chunks(kb, chunks) if chunks else 0
total = len(chunks)

cache_path = _lightrag_llm_cache_path(kb)
cache_mtime = None
new_complete = 0
cache_total_extract = 0
if cache_path.is_file():
    cache_mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    for v in cache.values():
        if not isinstance(v, dict) or v.get("cache_type") != "extract":
            continue
        cache_total_extract += 1
        if isinstance(v.get("create_time"), (int, float)):
            dt = datetime.fromtimestamp(v["create_time"], tz=timezone.utc)
            if dt >= task_start and "<|COMPLETE|>" in str(v.get("return") or ""):
                new_complete += 1

pct = (done * 100.0 / total) if total else 0.0
ts = time.strftime("%Y-%m-%d %H:%M:%S")
print(f"[{ts}] KB={kb_id} DOC={doc_id} file={doc.file_name!r}")
print(f"  db_status={doc.status}  lightrag={status}")
print(f"  ui_progress={done}/{total} ({pct:.1f}%)")
print(f"  new_complete_since_restart={new_complete}")
print(f"  cache_extract_entries={cache_total_extract}  cache_mtime={cache_mtime}")
if doc.status == "graph_indexed":
    print("  >>> DONE <<<")
elif total and new_complete == 0 and doc.status == "graph_indexing":
    print("  WARN: no new LLM cache since restart — may be stuck in embedding phase")
db.close()
PY
