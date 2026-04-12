import pytest
from pathlib import Path

from datum.services.project_manager import create_project, list_projects, get_project, ProjectInfo
from datum.services.filesystem import read_manifest


class TestCreateProject:
    def test_creates_directory_structure(self, tmp_path):
        info = create_project(
            projects_root=tmp_path,
            name="Auth Platform",
            slug="auth-platform",
            description="Auth system",
            tags=["auth", "security"],
        )
        project_dir = tmp_path / "auth-platform"
        assert project_dir.exists()
        assert (project_dir / "project.yaml").exists()
        assert (project_dir / "docs").is_dir()
        assert (project_dir / "attachments").is_dir()
        assert (project_dir / ".piq").is_dir()
        assert (project_dir / ".piq" / "manifest.yaml").exists()

    def test_project_yaml_content(self, tmp_path):
        info = create_project(tmp_path, "My Project", "my-project")
        import yaml
        data = yaml.safe_load((tmp_path / "my-project" / "project.yaml").read_text())
        assert data["name"] == "My Project"
        assert data["slug"] == "my-project"
        assert data["status"] == "active"
        assert "uid" in data
        assert "created" in data

    def test_duplicate_slug_raises(self, tmp_path):
        create_project(tmp_path, "First", "my-slug")
        with pytest.raises(FileExistsError):
            create_project(tmp_path, "Second", "my-slug")

    def test_returns_project_info(self, tmp_path):
        info = create_project(tmp_path, "Test", "test-project", tags=["a", "b"])
        assert info.name == "Test"
        assert info.slug == "test-project"
        assert info.tags == ["a", "b"]
        assert info.uid is not None

    def test_project_yaml_versioned_on_create(self, tmp_path):
        """Task 14: project.yaml gets v001 in .piq/project/versions/ on create."""
        create_project(tmp_path, "Test", "test-project")
        v001 = tmp_path / "test-project" / ".piq" / "project" / "versions" / "v001.yaml"
        assert v001.exists()
        import yaml
        data = yaml.safe_load(v001.read_text())
        assert data["name"] == "Test"


class TestListProjects:
    def test_empty(self, tmp_path):
        assert list_projects(tmp_path) == []

    def test_lists_all(self, tmp_path):
        create_project(tmp_path, "A", "a")
        create_project(tmp_path, "B", "b")
        projects = list_projects(tmp_path)
        slugs = {p.slug for p in projects}
        assert slugs == {"a", "b"}


class TestGetProject:
    def test_returns_info(self, tmp_path):
        create_project(tmp_path, "My Proj", "my-proj", description="desc")
        info = get_project(tmp_path, "my-proj")
        assert info is not None
        assert info.name == "My Proj"
        assert info.description == "desc"

    def test_missing_returns_none(self, tmp_path):
        assert get_project(tmp_path, "nonexistent") is None


class TestSlugValidation:
    """Finding 3: slug must be a safe single path component."""

    def test_rejects_path_traversal(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid project slug"):
            create_project(tmp_path, "Escaped", "../escaped-project")

    def test_rejects_slash(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid project slug"):
            create_project(tmp_path, "Nested", "a/b")

    def test_rejects_dot(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid project slug"):
            create_project(tmp_path, "Dotted", ".hidden")

    def test_rejects_empty(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid project slug"):
            create_project(tmp_path, "Empty", "")

    def test_rejects_uppercase(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid project slug"):
            create_project(tmp_path, "Upper", "MyProject")

    def test_get_project_validates_slug(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid project slug"):
            get_project(tmp_path, "../escape")
