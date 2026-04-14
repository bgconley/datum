from pathlib import Path

from datum.services.extraction import ExtractionResult, extract_text


class TestExtractText:
    def test_extract_markdown(self, tmp_path: Path):
        file_path = tmp_path / "test.md"
        file_path.write_text("---\ntitle: Test\n---\n# Hello\n\nSome content here.")

        result = extract_text(file_path)

        assert isinstance(result, ExtractionResult)
        assert result.text_kind == "raw"
        assert "# Hello" in result.content
        assert "Some content here." in result.content
        assert result.content_hash.startswith("sha256:")

    def test_extract_sql(self, tmp_path: Path):
        file_path = tmp_path / "schema.sql"
        file_path.write_text("CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT);")

        result = extract_text(file_path)

        assert result is not None
        assert result.text_kind == "raw"
        assert "CREATE TABLE users" in result.content

    def test_extract_yaml(self, tmp_path: Path):
        file_path = tmp_path / "config.yaml"
        file_path.write_text("key: value\nlist:\n  - a\n  - b\n")

        result = extract_text(file_path)

        assert result is not None
        assert "key: value" in result.content

    def test_extract_json(self, tmp_path: Path):
        file_path = tmp_path / "data.json"
        file_path.write_text('{"name": "test", "version": 1}')

        result = extract_text(file_path)

        assert result is not None
        assert '"name"' in result.content

    def test_strips_frontmatter_for_indexing(self, tmp_path: Path):
        file_path = tmp_path / "doc.md"
        file_path.write_text(
            "---\ntitle: My Doc\ntype: plan\ntags: [a, b]\n---\n# Content\n\nBody text."
        )

        result = extract_text(file_path)

        assert result is not None
        assert "title: My Doc" not in result.content
        assert "# Content" in result.content
        assert "Body text." in result.content

    def test_unsupported_extension(self, tmp_path: Path):
        file_path = tmp_path / "binary.dat"
        file_path.write_bytes(b"\x00\x01\x02\x03")

        result = extract_text(file_path)

        assert result is not None
        assert result.text_kind == "unsupported"

    def test_redacts_secrets_in_extracted_text(self, tmp_path: Path):
        file_path = tmp_path / "secret.md"
        file_path.write_text('Deploy with PASSWORD="super_secret_123" before release.')

        result = extract_text(file_path)

        assert result is not None
        assert "super_secret_123" not in result.content
        assert "[REDACTED:password]" in result.content
