"""Heading-aware chunking for extracted document text."""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

ENCODING = tiktoken.get_encoding("cl100k_base")
CHUNKING_PIPELINE_NAME = "heading-aware-chunking"
CHUNKING_PIPELINE_VERSION = "heading-aware-v1"
DEFAULT_MAX_TOKENS = 512
DEFAULT_OVERLAP_TOKENS = 50
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(slots=True)
class Chunk:
    content: str
    heading_path: list[str]
    start_char: int
    end_char: int
    start_line: int
    end_line: int
    token_count: int
    chunk_index: int = 0


@dataclass(slots=True)
class Section:
    content: str
    heading_path: list[str]
    start_char: int
    end_char: int
    start_line: int
    end_line: int


def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))


def chunk_text(
    text: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    if not text.strip():
        return []

    chunks: list[Chunk] = []

    for section in _split_by_headings(text):
        token_count = count_tokens(section.content)
        if token_count <= max_tokens:
            chunks.append(
                Chunk(
                    content=section.content,
                    heading_path=section.heading_path,
                    start_char=section.start_char,
                    end_char=section.end_char,
                    start_line=section.start_line,
                    end_line=section.end_line,
                    token_count=token_count,
                )
            )
            continue

        chunks.extend(
            _split_by_tokens(
                content=section.content,
                heading_path=section.heading_path,
                base_start_char=section.start_char,
                base_start_line=section.start_line,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens,
            )
        )

    for index, chunk in enumerate(chunks):
        chunk.chunk_index = index
    return chunks


def _split_by_headings(text: str) -> list[Section]:
    lines = text.splitlines(keepends=True)
    if not lines:
        return []

    sections: list[Section] = []
    heading_stack: list[tuple[int, str]] = []
    current_path: list[str] = []
    current_lines: list[str] = []
    current_start_char = 0
    current_start_line = 1
    offset = 0
    in_fence = False
    saw_heading = False

    def flush(end_char: int, end_line: int) -> None:
        if not current_lines:
            return
        content = "".join(current_lines)
        if not content.strip():
            return
        sections.append(
            Section(
                content=content,
                heading_path=list(current_path),
                start_char=current_start_char,
                end_char=end_char,
                start_line=current_start_line,
                end_line=end_line,
            )
        )

    for line_number, line in enumerate(lines, start=1):
        stripped = line.rstrip("\n")
        if stripped.startswith("```"):
            in_fence = not in_fence

        heading_match = None if in_fence else HEADING_PATTERN.match(stripped)
        if heading_match:
            saw_heading = True
            flush(offset, line_number - 1)

            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack = [(lvl, txt) for lvl, txt in heading_stack if lvl < level]
            heading_stack.append((level, title))
            current_path = [txt for _, txt in heading_stack]
            current_lines = []
            current_start_char = offset
            current_start_line = line_number

        current_lines.append(line)
        offset += len(line)

    flush(offset, len(lines))

    if not saw_heading and text.strip():
        return [
            Section(
                content=text,
                heading_path=[],
                start_char=0,
                end_char=len(text),
                start_line=1,
                end_line=len(text.splitlines()),
            )
        ]

    return sections


def _split_by_tokens(
    *,
    content: str,
    heading_path: list[str],
    base_start_char: int,
    base_start_line: int,
    max_tokens: int,
    overlap_tokens: int,
) -> list[Chunk]:
    tokens = ENCODING.encode(content)
    chunks: list[Chunk] = []
    start = 0

    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        window = tokens[start:end]
        window_text = ENCODING.decode(window)

        prefix = ENCODING.decode(tokens[:start])
        start_char = base_start_char + len(prefix)
        end_char = start_char + len(window_text)
        start_line = base_start_line + prefix.count("\n")
        end_line = start_line + window_text.count("\n")

        chunks.append(
            Chunk(
                content=window_text,
                heading_path=list(heading_path),
                start_char=start_char,
                end_char=end_char,
                start_line=start_line,
                end_line=end_line,
                token_count=len(window),
            )
        )

        if end >= len(tokens):
            break
        start = max(end - overlap_tokens, start + 1)

    return chunks
