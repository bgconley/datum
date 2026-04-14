from datum.services.sessions import (
    SessionMetadata,
    append_session_note,
    create_session_note,
    find_session_note,
    list_session_notes,
    parse_session_frontmatter,
)


def test_create_and_append_session_note(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    created = create_session_note(
        project_dir,
        SessionMetadata(
            session_id="sess-1",
            agent_name="codex",
            summary="Implement phase 6",
            content="## Work\nDid the work.",
            files_touched=["backend/datum/main.py"],
        ),
    )
    rel_path = created.relative_to(project_dir).as_posix()
    assert rel_path.startswith("docs/sessions/")

    parsed = parse_session_frontmatter(created.read_text())
    assert parsed.session_id == "sess-1"
    assert parsed.agent_name == "codex"
    assert "Did the work." in parsed.content

    append_session_note(
        project_dir,
        created,
        new_content="Added tests.",
        new_files=["backend/tests/test_sessions.py"],
        new_commands=["pytest -q"],
        new_next_steps=["Run integration"],
    )
    updated = parse_session_frontmatter(created.read_text())
    assert "Added tests." in updated.content
    assert "backend/tests/test_sessions.py" in updated.files_touched
    assert "pytest -q" in updated.commands_run
    assert updated.ended_at is not None

    assert find_session_note(project_dir, "sess-1") == created
    sessions = list_session_notes(project_dir)
    assert sessions[0]["session_id"] == "sess-1"
