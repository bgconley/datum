"""Tests for prompt formatting."""


from qwen3_embedder.core.prompt import (
    INSTRUCTION_TEMPLATES,
    PromptFormatter,
    format_document,
    format_query,
    get_detailed_instruct,
)


class TestGetDetailedInstruct:
    """Tests for get_detailed_instruct function."""

    def test_basic_format(self):
        """Test basic instruction + query format."""
        result = get_detailed_instruct("Retrieve passages", "What is ML?")
        assert result == "Instruct: Retrieve passages\nQuery:What is ML?"

    def test_empty_query(self):
        """Test with empty query."""
        result = get_detailed_instruct("Task", "")
        assert result == "Instruct: Task\nQuery:"

    def test_multiline_query(self):
        """Test with multiline query."""
        query = "Line 1\nLine 2"
        result = get_detailed_instruct("Task", query)
        assert "Line 1\nLine 2" in result


class TestFormatQuery:
    """Tests for format_query function."""

    def test_with_custom_instruction(self):
        """Test with custom instruction."""
        result = format_query("test query", instruction="Custom instruction")
        assert "Custom instruction" in result
        assert "test query" in result

    def test_with_task_type(self):
        """Test with task type."""
        result = format_query("test query", task_type="retrieval")
        assert "retrieve relevant passages" in result.lower()

    def test_default_task_type(self):
        """Test default task type is retrieval."""
        result = format_query("test query")
        assert "retrieve" in result.lower()

    def test_custom_instruction_overrides_task_type(self):
        """Test custom instruction overrides task type."""
        result = format_query(
            "query",
            instruction="My custom instruction",
            task_type="classification"
        )
        assert "My custom instruction" in result
        assert "classify" not in result.lower()


class TestFormatDocument:
    """Tests for format_document function."""

    def test_returns_unchanged(self):
        """Test document is returned unchanged."""
        doc = "This is a document about ML."
        result = format_document(doc)
        assert result == doc

    def test_empty_document(self):
        """Test empty document."""
        result = format_document("")
        assert result == ""


class TestPromptFormatter:
    """Tests for PromptFormatter class."""

    def test_default_initialization(self):
        """Test default initialization."""
        formatter = PromptFormatter()
        assert formatter.default_task_type == "retrieval"
        assert formatter.default_instruction is None

    def test_custom_instruction(self):
        """Test with custom default instruction."""
        formatter = PromptFormatter(default_instruction="Custom default")
        queries = formatter.format_queries(["q1", "q2"])

        for q in queries:
            assert "Custom default" in q

    def test_format_queries(self):
        """Test formatting multiple queries."""
        formatter = PromptFormatter()
        queries = ["query 1", "query 2", "query 3"]
        formatted = formatter.format_queries(queries)

        assert len(formatted) == 3
        for f in formatted:
            assert "Instruct:" in f
            assert "Query:" in f

    def test_format_documents(self):
        """Test formatting multiple documents."""
        formatter = PromptFormatter()
        docs = ["doc 1", "doc 2"]
        formatted = formatter.format_documents(docs)

        assert len(formatted) == 2
        assert formatted == docs

    def test_format_mixed(self):
        """Test formatting mixed queries and documents."""
        formatter = PromptFormatter()
        texts = ["query", "document", "query 2"]
        is_query = [True, False, True]

        formatted = formatter.format_mixed(texts, is_query)

        assert len(formatted) == 3
        assert "Instruct:" in formatted[0]  # query
        assert "Instruct:" not in formatted[1]  # document
        assert "Instruct:" in formatted[2]  # query


class TestDatumSemantics:
    """Datum-specific semantics: queries are prefixed, documents are not."""

    def test_document_formatting_stays_plain(self):
        doc = "CREATE TABLE documents (id uuid primary key)"
        assert format_document(doc) == doc

    def test_query_formatting_adds_instruction(self):
        query = format_query("where is the migration?", instruction="Find operational docs")
        assert query.startswith("Instruct: Find operational docs")


class TestInstructionTemplates:
    """Tests for instruction templates."""

    def test_all_templates_exist(self):
        """Test all expected templates exist."""
        expected = [
            "retrieval",
            "semantic_similarity",
            "classification",
            "clustering",
            "code_retrieval",
            "qa",
            "default",
        ]
        for key in expected:
            assert key in INSTRUCTION_TEMPLATES

    def test_templates_are_strings(self):
        """Test all templates are non-empty strings."""
        for _key, value in INSTRUCTION_TEMPLATES.items():
            assert isinstance(value, str)
            assert len(value) > 0
