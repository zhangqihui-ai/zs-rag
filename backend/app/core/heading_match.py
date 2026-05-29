"""章节标题识别：兼容 MinerU Markdown 加粗（**一、…**）等格式。"""

from __future__ import annotations

import re

_CN_NUM = r"[一二三四五六七八九十百千]+"
_ENUM_LIST_LINE = re.compile(r"^\d+\s*[、.．)）]\s*")
_CN_CHAPTER_LINE = re.compile(rf"^(?:第\s*)?{_CN_NUM}\s*[、.．]")
_CN_SECTION_LINE = re.compile(rf"^[(（]\s*{_CN_NUM}\s*[)）]")
_MARKDOWN_INLINE_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")


def strip_markdown_inline(text: str) -> str:
    """去掉行内 ** / __ 包裹，便于章节正则匹配。"""
    t = (text or "").strip()
    if not t:
        return ""
    prev = None
    while prev != t:
        prev = t
        t = _MARKDOWN_INLINE_RE.sub(lambda m: m.group(1) or m.group(2) or "", t)
    return t.strip()


def normalize_heading_match_text(text: str) -> str:
    return strip_markdown_inline(text).replace("\u3000", " ").strip()


def heading_starts_body(text: str) -> bool:
    """正文章节标题（一、 / （一） / 第X章），区别于封面主标题。"""
    t = normalize_heading_match_text(text)
    if not t:
        return False
    if _ENUM_LIST_LINE.match(t):
        return True
    return heading_starts_cn_section(text)


def heading_starts_cn_section(text: str) -> bool:
    """中文节级标题（一、二、三、 / （一） / 第X章），不含 1、2、3 列表项。"""
    t = normalize_heading_match_text(text)
    if not t:
        return False
    if _CN_CHAPTER_LINE.match(t) or _CN_SECTION_LINE.match(t):
        return True
    if re.match(r"^第\s*\d+\s*[章节篇部条款]", t):
        return True
    return False


def is_inline_enumeration_marker(
    line: str,
    prev_line: str | None = None,
    *,
    short_max: int = 40,
) -> bool:
    """括号中文枚举（（一）（二）…）作为条文/段内列表项，而非节级标题硬切边界。

    法条 / 制度文中「…如下：（一）…（二）…」属于同一条文的列表项，
    不应被当作节标题逐项硬切。判定为内联枚举（不作为切分边界）的情形：
    - 该行确为 （X） 括号中文枚举开头；且
      - 紧邻上一行以 ：/: 结尾（引导句，如「…如下：」），或
      - 该行较短（典型短列表项，长度 <= short_max）。

    注意：仅放宽括号枚举（（一）），不影响 `一、`、`第X章/节/条` 的硬切。
    """
    t = normalize_heading_match_text(line)
    if not t or not _CN_SECTION_LINE.match(t):
        return False
    if prev_line is not None:
        p = normalize_heading_match_text(prev_line).rstrip()
        if p.endswith(("：", ":")):
            return True
    return len(t) <= short_max
