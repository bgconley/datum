
import pytest
from httpx import ASGITransport, AsyncClient

from datum.config import settings


@pytest.fixture
def tmp_projects(tmp_path):
    """Provide a temporary projects root for tests."""
    projects = tmp_path / "projects"
    projects.mkdir()
    settings.projects_root = projects
    return projects


@pytest.fixture
def tmp_blobs(tmp_path):
    """Provide a temporary blobs root for tests."""
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    settings.blobs_root = blobs
    return blobs


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    from datum.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
