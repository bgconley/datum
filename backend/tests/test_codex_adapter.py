import os
import stat

ADAPTERS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "adapters", "codex"
)


def test_wrapper_exists_and_is_executable():
    path = os.path.join(ADAPTERS_DIR, "datum-codex-wrapper.sh")
    assert os.path.exists(path)
    assert os.stat(path).st_mode & stat.S_IXUSR


def test_agents_template_exists():
    path = os.path.join(ADAPTERS_DIR, "AGENTS.md.template")
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as handle:
        content = handle.read()
    assert "get_project_context" in content
    assert "search_project_memory" in content
    assert "{{PROJECT_SLUG}}" in content
