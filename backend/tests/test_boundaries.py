from datum.services.boundaries import ContentKind, wrap_content


def test_wrap_content_returns_boundary_metadata():
    wrapped = wrap_content("hello", ContentKind.DOCUMENT)
    assert wrapped["content"] == "hello"
    assert wrapped["content_kind"] == "retrieved_project_document"
    assert "facts" in wrapped["trusted_for"]
    assert "agent_instructions" in wrapped["not_trusted_for"]
