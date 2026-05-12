"""从已缓存的 MinerU 响应 JSON 里读 content_list，跑一次分块流水线看 chunks。"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.chunking_engine import (  # noqa: E402
    adapt_chunk_size_for_small_doc,
    merge_adjacent_segments_by_budget,
    merge_leading_preamble_segments,
)
from app.core.mineru_gateway import MineruResult, _extract_content_list_and_md  # noqa: E402
from app.core.text_chunker import chunk_segments  # noqa: E402


def main(payload_path: str) -> None:
    with open(payload_path) as f:
        payload = json.load(f)
    cl, md = _extract_content_list_and_md(payload)
    result = MineruResult(content_list=cl, markdown=md, source_file_name="cached.pdf")
    doc = result.to_parsed_document()
    print(f"segments: {len(doc.segments)} chars: {doc.char_count} "
          f"heading: {doc.metadata.get('heading_count')}", flush=True)

    segs = merge_leading_preamble_segments(doc.segments)
    cs, co = adapt_chunk_size_for_small_doc(segs, chunk_size=512, chunk_overlap=50)
    print(f"adapted chunk_size/overlap: {cs}/{co}", flush=True)
    segs = merge_adjacent_segments_by_budget(segs, budget=cs)
    print(f"after merge segments: {len(segs)}", flush=True)
    chunks = chunk_segments(segs, chunk_size=cs, chunk_overlap=co)
    print(f"final chunks: {len(chunks)}", flush=True)

    for i, ch in enumerate(chunks[:8]):
        path = ch.heading_path or ""
        body = ch.content.replace("\n", " / ")
        print(f"[chunk {i}] len={ch.char_count} path={path!r}", flush=True)
        print(f"    {body[:160]}", flush=True)

    by_path = Counter(c.heading_path for c in chunks)
    print("top heading_paths:", flush=True)
    for path, count in sorted(by_path.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  [{count}] {path}", flush=True)

    lens = [c.char_count for c in chunks]
    if lens:
        print(
            f"chunk length: min={min(lens)} max={max(lens)} "
            f"avg={sum(lens)//len(lens)} median={sorted(lens)[len(lens)//2]}",
            flush=True,
        )


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mineru_first_resp.json"
    main(path)
