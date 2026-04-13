"""
Prompt Builder - Constructs instruction-prefixed prompts for queries.

Qwen3-Embedding models support instruction-aware embeddings where queries
are prefixed with task descriptions to improve retrieval quality.

Key difference from reranker:
- Reranker: Uses chat format with system prompt and <think> tags
- Embedder: Uses simple "Instruct: {task}\nQuery:{query}" format for queries
- Documents: No instruction prefix needed - embed as-is
"""

import logging

logger = logging.getLogger(__name__)


# Default instruction templates for common tasks
INSTRUCTION_TEMPLATES = {
    "retrieval": "Given a web search query, retrieve relevant passages that answer the query",
    "semantic_similarity": "Retrieve semantically similar text",
    "classification": "Classify the following text",
    "clustering": "Represent this text for clustering",
    "code_retrieval": "Given a natural language query, retrieve relevant code snippets",
    "qa": "Given a question, retrieve passages that answer the question",
    "summarization": "Given a document, retrieve its most relevant summary",
    "default": "Given a web search query, retrieve relevant passages that answer the query",
}


def get_detailed_instruct(task_description: str, query: str) -> str:
    """
    Build instruction-prefixed prompt for query embeddings.

    Format: "Instruct: {task_description}\nQuery:{query}"

    Note: Documents should NOT use this function - embed them as-is.

    Args:
        task_description: One-sentence task description
        query: The actual query text

    Returns:
        Formatted prompt string

    Example:
        >>> get_detailed_instruct("Retrieve relevant passages", "What is ML?")
        'Instruct: Retrieve relevant passages\\nQuery:What is ML?'
    """
    return f"Instruct: {task_description}\nQuery:{query}"


def format_query(
    query: str,
    instruction: str | None = None,
    task_type: str = "retrieval",
) -> str:
    """
    Format query with appropriate instruction prefix.

    Args:
        query: Raw query text
        instruction: Custom instruction (overrides task_type)
        task_type: Predefined task type for default instruction

    Returns:
        Instruction-prefixed query
    """
    if instruction is None:
        instruction = INSTRUCTION_TEMPLATES.get(task_type, INSTRUCTION_TEMPLATES["default"])

    return get_detailed_instruct(instruction, query)


def format_document(document: str) -> str:
    """
    Format document for embedding.

    Documents do NOT need instruction prefix - embed as-is.
    This function exists for consistency and potential future processing.

    Args:
        document: Raw document text

    Returns:
        Document text (unchanged)
    """
    return document


class PromptFormatter:
    """
    Stateful prompt formatter with configurable defaults.

    Use this class when you need consistent formatting across multiple
    calls with the same instruction settings.
    """

    def __init__(
        self,
        default_instruction: str | None = None,
        default_task_type: str = "retrieval",
    ):
        """
        Initialize prompt formatter.

        Args:
            default_instruction: Custom default instruction (overrides task_type)
            default_task_type: Default task type for instruction lookup
        """
        self.default_instruction = default_instruction
        self.default_task_type = default_task_type

    def format_queries(
        self,
        queries: list[str],
        instruction: str | None = None,
    ) -> list[str]:
        """
        Format multiple queries with instruction prefix.

        Args:
            queries: List of raw query strings
            instruction: Optional instruction override

        Returns:
            List of formatted query strings
        """
        inst = instruction or self.default_instruction
        return [format_query(q, inst, self.default_task_type) for q in queries]

    def format_documents(self, documents: list[str]) -> list[str]:
        """
        Format multiple documents (no change).

        Args:
            documents: List of raw document strings

        Returns:
            List of document strings (unchanged)
        """
        return [format_document(d) for d in documents]

    def format_mixed(
        self,
        texts: list[str],
        is_query: list[bool],
        instruction: str | None = None,
    ) -> list[str]:
        """
        Format a mixed batch of queries and documents.

        Args:
            texts: List of text strings
            is_query: Boolean mask indicating which texts are queries
            instruction: Optional instruction for queries

        Returns:
            List of formatted strings
        """
        result = []
        inst = instruction or self.default_instruction

        for text, query_flag in zip(texts, is_query, strict=False):
            if query_flag:
                result.append(format_query(text, inst, self.default_task_type))
            else:
                result.append(format_document(text))

        return result
