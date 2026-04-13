from fastapi.testclient import TestClient

from gliner_ner_service.app import create_app
from gliner_ner_service.backend import GlinerBackend
from gliner_ner_service.config import Settings


class _FakeBackend(GlinerBackend):
    def __init__(self) -> None:
        super().__init__(model_id="fake-gliner")
        self._model = object()

    def extract(self, text: str, *, labels: list[str], threshold: float):
        assert text == "Use PostgreSQL."
        assert labels == ["technology"]
        assert threshold == 0.5
        return [
            {"text": "PostgreSQL", "label": "technology", "start": 4, "end": 14, "score": 0.95}
        ]


def test_health_and_extract_routes():
    app = create_app(
        settings=Settings(
            host="127.0.0.1",
            port=8012,
            model_id="fake-gliner",
            default_threshold=0.5,
        ),
        backend=_FakeBackend(),
    )
    client = TestClient(app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["loaded"] is True
    assert health.json()["model_id"] == "fake-gliner"

    extract = client.post(
        "/extract",
        json={
            "text": "Use PostgreSQL.",
            "labels": ["technology"],
        },
    )
    assert extract.status_code == 200
    assert extract.json()[0]["label"] == "technology"
