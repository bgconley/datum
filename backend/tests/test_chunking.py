from datum.services.chunking import Chunk, chunk_text


class TestChunkText:
    def test_single_section_fits_in_one_chunk(self):
        text = "# Title\n\nShort paragraph."

        chunks = chunk_text(text, max_tokens=512)

        assert len(chunks) == 1
        assert isinstance(chunks[0], Chunk)
        assert chunks[0].heading_path == ["Title"]
        assert "Short paragraph." in chunks[0].content

    def test_splits_by_headings(self):
        text = "# H1\n\nContent A.\n\n## H2\n\nContent B.\n\n## H3\n\nContent C."

        chunks = chunk_text(text, max_tokens=512)

        assert len(chunks) == 3
        assert chunks[0].heading_path == ["H1"]
        assert chunks[1].heading_path == ["H1", "H2"]
        assert chunks[2].heading_path == ["H1", "H3"]

    def test_long_section_splits_with_overlap(self):
        text = "# Title\n\n" + ("word " * 600)

        chunks = chunk_text(text, max_tokens=100, overlap_tokens=20)

        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.token_count <= 100

    def test_preserves_char_offsets(self):
        text = "# H1\n\nFirst section.\n\n## H2\n\nSecond section."

        chunks = chunk_text(text, max_tokens=512)

        for chunk in chunks:
            assert text[chunk.start_char:chunk.end_char].strip() == chunk.content.strip()

    def test_preserves_line_numbers(self):
        text = "# H1\n\nLine 3 content.\n\n## H2\n\nLine 6 content."

        chunks = chunk_text(text, max_tokens=512)

        assert chunks[0].start_line >= 1
        assert chunks[1].start_line > chunks[0].end_line

    def test_empty_text(self):
        assert chunk_text("", max_tokens=512) == []

    def test_no_headings(self):
        text = "Just a plain paragraph with no headings at all."

        chunks = chunk_text(text, max_tokens=512)

        assert len(chunks) == 1
        assert chunks[0].heading_path == []

    def test_code_blocks_not_split(self):
        text = "# Code\n\n```python\ndef foo():\n    return 'bar'\n```\n\nAfter code."

        chunks = chunk_text(text, max_tokens=512)

        assert len(chunks) == 1
        assert "def foo" in chunks[0].content
