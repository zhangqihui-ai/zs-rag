"""整表分段与行批合并。"""

from app.core.document_parser import (
    MAX_TABLE_ROW_SEGMENT_CHARS,
    ParsedSegment,
    build_table_segments_from_rows,
    build_table_segments_smart,
    prepend_table_context,
)


def _run(segments_fn) -> list[ParsedSegment]:
    offset = [0]
    parts: list[str] = []
    rows = [
        ["能力基本信息", "能力名称", "政务数据智能编目系统能力"],
        ["服务名称", "a", "b"],
        ["申请单位", "河南公司", ""],
    ]
    body = """| 能力基本信息 | 能力名称 | 政务数据智能编目系统能力 |
| --- | --- | --- |
| 服务名称 | a | b |
| 申请单位 | 河南公司 | |"""
    return segments_fn(rows, body, offset, parts)


def test_whole_table_when_body_fits():
    def fn(rows, body, offset, parts):
        return build_table_segments_smart(
            rows, 0, offset, parts, None, table_body=body, table_body_html="<table></table>"
        )

    segs = _run(fn)
    assert len(segs) == 1
    assert segs[0].metadata.get("table_role") == "body"
    assert "| 服务名称 |" in segs[0].text


def test_row_batching_without_whole_body():
    offset = [0]
    parts: list[str] = []
    rows = [["h1", "h2"]] + [[f"r{i}c1", f"r{i}c2"] for i in range(60)]
    segs = build_table_segments_from_rows(rows, 0, offset, parts, None, row_batch_size=1)
    assert len(segs) == 61  # overview + 60 rows

    offset2 = [0]
    parts2: list[str] = []
    segs2 = build_table_segments_smart(rows, 0, offset2, parts2, None)
    row_segs = [s for s in segs2 if (s.metadata or {}).get("table_role") == "row"]
    assert len(row_segs) < 60
    assert all(len(s.text) <= MAX_TABLE_ROW_SEGMENT_CHARS * 12 for s in row_segs)


def test_wide_table_char_budget_batching():
    header = ["数据目录名称", "提供方", "共享类型", "共享方式", "共享条件", "更新频率"]
    wide_row = [f"{col}字段内容示例" * 8 for col in header]
    rows = [header] + [list(wide_row) for _ in range(120)]
    offset = [0]
    parts: list[str] = []
    segs = build_table_segments_smart(rows, 0, offset, parts, "Sheet1")
    row_segs = [s for s in segs if (s.metadata or {}).get("table_role") == "row"]
    assert len(row_segs) > 12
    assert len(row_segs) < 120
    for seg in row_segs:
        assert len(seg.text) <= MAX_TABLE_ROW_SEGMENT_CHARS * 1.2
        assert (seg.metadata or {}).get("table_row_batch_size", 99) <= 10


def test_whole_table_includes_context_prefix():
    offset = [0]
    parts: list[str] = []
    rows = [["场景", "设备配置"], ["门诊", "摄像头"]]
    body = "| 场景 | 设备配置 |\n| --- | --- |\n| 门诊 | 摄像头 |"
    prefix = "附件2\n\n医保智能场景监控终端设备\n\n基本配置方案表（参考）"
    segs = build_table_segments_smart(
        rows,
        0,
        offset,
        parts,
        None,
        table_body=body,
        context_prefix=prefix,
    )
    assert len(segs) == 1
    assert "附件2" in segs[0].text
    assert "基本配置方案表（参考）" in segs[0].text
    assert "| 门诊 |" in segs[0].text


def test_prepend_table_context_dedupes():
    body = "附件2\n\n| A | B |"
    out = prepend_table_context(body, "附件2")
    assert out == body
