from datum.services.context import ContextConfig, DetailLevel, build_project_context, count_tokens


def test_build_project_context_respects_budget_and_includes_records(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "project.yaml").write_text("name: Project\nslug: project\n")

    docs_dir = project_dir / "docs"
    docs_dir.mkdir()
    (docs_dir / "overview.md").write_text(
        "---\ntitle: Overview\ntype: plan\n---\n\nProject overview paragraph.\n\nSecond."
    )

    records_dir = project_dir / ".piq" / "records"
    (records_dir / "decisions").mkdir(parents=True)
    (records_dir / "requirements").mkdir(parents=True)
    (records_dir / "open-questions").mkdir(parents=True)
    (records_dir / "decisions" / "dec.yaml").write_text("uid: dec_1\ntitle: Use API keys\n")
    (records_dir / "requirements" / "req.yaml").write_text("uid: req_1\ntitle: Add MCP\n")
    (records_dir / "open-questions" / "oq.yaml").write_text("uid: oq_1\nquestion: What next?\n")

    payload = build_project_context(
        project_dir,
        ContextConfig(detail=DetailLevel.STANDARD, max_tokens=400, limit_per_section=1),
    )

    assert payload["project"]["name"] == "Project"
    assert payload["documents"][0]["summary"] == "Project overview paragraph."
    assert len(payload["decisions"]) == 1
    assert len(payload["requirements"]) == 1
    assert len(payload["open_questions"]) == 1
    assert count_tokens(str(payload)) <= 400
