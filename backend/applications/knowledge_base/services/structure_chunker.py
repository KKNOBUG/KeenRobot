# -*- coding: utf-8 -*-
"""方案 B：结构/段落/节级分块（B1～B5）。"""

import re
from dataclasses import dataclass
from typing import List, Optional

from langchain_core.documents import Document as LangchainDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

# B1：章节/标题行（行级判断，避免正文「第N条……」误切）
def _is_section_heading(line: str) -> bool:
    line = line.strip()
    if not line or len(line) > 120:
        return False
    if re.match(r"^第[0-9一二三四五六七八九十百]+[章节篇部]", line):
        return True
    if re.match(r"^第[0-9一二三四五六七八九十百]+条", line) and len(line) <= 60:
        return True
    if re.match(r"^[0-9]+(?:\.[0-9]+)+[\s、.．]", line) and len(line) <= 80:
        return True
    if re.match(r"^#{1,6}\s+", line):
        return True
    if re.match(r"^[一二三四五六七八九十]+[、.．]", line) and len(line) <= 60:
        return True
    return False
# B4：Markdown 表格块
_TABLE_BLOCK = re.compile(r"(?:^\|.+\|\s*\n)+", re.M)


@dataclass
class _Section:
    title: str
    body: str
    page_number: Optional[int]


def _page_number(page: LangchainDocument) -> Optional[int]:
    raw = page.metadata.get("page")
    return int(raw) + 1 if raw is not None else None


def _effective_overlap(chunk_size: int, chunk_overlap: Optional[int]) -> int:
    """B3：overlap = min(200, chunk_size * 0.25)，且不超过 chunk_size/2。"""
    b3 = min(200, int(chunk_size * 0.25))
    overlap = max(b3, chunk_overlap or 0)
    return min(overlap, chunk_size // 2)


def _split_table_blocks(text: str) -> List[str]:
    """B4：抽出 Markdown 表格为独立片段，其余文本合并返回。"""
    text = text.strip()
    if not text:
        return []

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if lines and all(ln.strip().startswith("|") for ln in lines):
        return [text]

    parts: List[str] = []
    last = 0
    for match in _TABLE_BLOCK.finditer(text):
        if match.start() > last:
            parts.append(text[last:match.start()])
        parts.append(match.group(0))
        last = match.end()
    if last < len(text):
        parts.append(text[last:])
    return [p.strip() for p in parts if p and p.strip()]


def _section_starts(text: str) -> List[tuple[int, str]]:
    starts: List[tuple[int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped and _is_section_heading(stripped):
            starts.append((offset, stripped))
        offset += len(line)
    return starts


def _sections_from_block(text: str, page_number: Optional[int]) -> List[_Section]:
    text = text.strip()
    if not text:
        return []

    if _TABLE_BLOCK.search(text) and text.startswith("|"):
        return [_Section(title="【表格】", body=text, page_number=page_number)]

    starts = _section_starts(text)
    if len(starts) >= 2:
        sections: List[_Section] = []
        for i, (pos, title) in enumerate(starts):
            end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
            body = text[pos + len(title): end].strip()
            sections.append(_Section(title=title, body=body or title, page_number=page_number))
        return sections

    if len(starts) == 1:
        pos, title = starts[0]
        body = text[pos + len(title):].strip()
        return [_Section(title=title, body=body or title, page_number=page_number)]

    # B2：无结构标题时按段落切节
    return [
        _Section(title="", body=para, page_number=page_number)
        for para in (p.strip() for p in text.split("\n\n"))
        if para
    ]


def _with_title(title: str, body: str) -> str:
    body = (body or "").strip()
    title = (title or "").strip()
    if not body:
        return title
    if not title:
        return body
    if body.startswith(title):
        return body
    return f"{title}\n{body}"


def _chunk_section(section: _Section, chunk_size: int, overlap: int) -> List[str]:
    """B5：节内 ≤ chunk_size 整节一块；超长节在句边界二次切，每块带标题（B1）。"""
    body = (section.body or "").strip()
    if not body and not section.title:
        return []

    full = _with_title(section.title, body)
    # B4：表格尽量整表入库（上限 8000 字）
    if section.title == "【表格】" and len(full) <= 8000:
        return [full]
    if len(full) <= chunk_size:
        return [full]

    title_prefix = f"{section.title}\n" if section.title else ""
    body_budget = max(chunk_size - len(title_prefix), chunk_size // 2)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=body_budget,
        chunk_overlap=min(overlap, body_budget // 2),
        separators=["\n\n", "\n", "。", "；", "，", " ", ""],
    )
    return [
        _with_title(section.title, part)
        for part in splitter.split_text(body)
        if part and part.strip()
    ]


def structure_chunk_pages(
        pages: List[LangchainDocument],
        chunk_size: int,
        chunk_overlap: Optional[int] = None,
) -> List[dict]:
    """
    将 PDF 页列表结构分块（方案 B，扁平 chunk 列表）。

    Returns:
        [{"content": str, "page_number": int|None}, ...]
    """
    overlap = _effective_overlap(chunk_size, chunk_overlap)
    chunks: List[dict] = []

    for page in pages:
        page_no = _page_number(page)
        raw = (page.page_content or "").strip()
        if not raw:
            continue

        for block in _split_table_blocks(raw):
            for section in _sections_from_block(block, page_no):
                for content in _chunk_section(section, chunk_size, overlap):
                    chunks.append({"content": content, "page_number": page_no})

    return chunks


def structure_parent_index_pages(
        pages: List[LangchainDocument],
        index_chunk_size: int,
        chunk_overlap: Optional[int] = None,
) -> List[dict]:
    """
    方案 C：节级 parent + 索引用 child。

    Returns:
        [{
            "page_number": int|None,
            "parent_content": str,
            "index_chunks": [str, ...],
        }, ...]
    """
    overlap = _effective_overlap(index_chunk_size, chunk_overlap)
    groups: List[dict] = []

    for page in pages:
        page_no = _page_number(page)
        raw = (page.page_content or "").strip()
        if not raw:
            continue

        for block in _split_table_blocks(raw):
            for section in _sections_from_block(block, page_no):
                body = (section.body or "").strip()
                if not body and not section.title:
                    continue
                parent_content = _with_title(section.title, body)
                if len(parent_content) <= index_chunk_size:
                    index_chunks = [parent_content]
                else:
                    index_chunks = _chunk_section(section, index_chunk_size, overlap)
                if not index_chunks:
                    continue
                groups.append(
                    {
                        "page_number": page_no,
                        "parent_content": parent_content,
                        "index_chunks": index_chunks,
                    }
                )

    return groups
