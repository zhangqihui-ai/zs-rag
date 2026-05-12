"""联调 smoke：真实 PDF 走完整 parse_document + 分块流水线，确认 MinerU 路径端到端可用。"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.chunking_engine import (  # noqa: E402
    adapt_chunk_size_for_small_doc,
    merge_adjacent_segments_by_budget,
    merge_leading_preamble_segments,
)
from app.core.document_parser import parse_document  # noqa: E402
from app.core.text_chunker import chunk_segments  # noqa: E402


def log(msg: str) -> None:
    print(msg, flush=True)


def main(pdf_path: str) -> None:
    with open(pdf_path, "rb") as f:
        data = f.read()

    t0 = time.time()
    pd = parse_document(pdf_path.rsplit("/", 1)[-1], data, log=log)
    log(
        f"parse done: backend={pd.metadata.get('parser_backend')} "
        f"segments={len(pd.segments)} chars={pd.char_count} "
        f"heading={pd.metadata.get('heading_count')} table={pd.metadata.get('table_count')} "
        f"elapsed={round(time.time()-t0, 1)}s"
    )

    segs = merge_leading_preamble_segments(pd.segments)
    cs, co = adapt_chunk_size_for_small_doc(segs, chunk_size=512, chunk_overlap=50)
    log(f"adapted chunk_size/overlap: {cs}/{co}")
    segs = merge_adjacent_segments_by_budget(segs, budget=cs)
    log(f"after merge: {len(segs)} segments")
    chunks = chunk_segments(segs, chunk_size=cs, chunk_overlap=co)
    log(f"final chunks: {len(chunks)}")

    for i, ch in enumerate(chunks[:6]):
        path = ch.heading_path or ""
        body = ch.content.replace("\n", " / ")
        log(f"[chunk {i}] len={ch.char_count} path={path!r}")
        log(f"    {body[:160]}")

    by_path = Counter(c.heading_path for c in chunks)
    log("top heading_paths:")
    for path, count in sorted(by_path.items(), key=lambda kv: -kv[1])[:10]:
        log(f"  [{count}] {path}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/app/storage/knowledge_files/1/2/3/original.pdf"
    main(path)
