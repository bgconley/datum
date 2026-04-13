from gliner_ner_service.backend import GlinerBackend


class _FakeModel:
    def __init__(self) -> None:
        self.device = None

    def to(self, device: str):
        self.device = device
        return self

    def predict_entities(self, text, labels, threshold):
        assert text == "Use PostgreSQL and Redis."
        assert labels == ["technology"]
        assert threshold == 0.6
        return [
            {"text": "PostgreSQL", "label": "Technology", "start": 4, "end": 14, "score": 0.95},
            {"text": "Redis", "label": "Technology", "start": 19, "end": 24, "score": 0.91},
        ]


class _FakeGLiNER:
    @staticmethod
    def from_pretrained(model_id):
        assert model_id == "knowledgator/gliner-bi-large-v2.0"
        return _FakeModel()


def test_backend_load_and_extract(monkeypatch):
    monkeypatch.setattr("gliner_ner_service.backend._load_gliner_class", lambda: _FakeGLiNER)

    backend = GlinerBackend(
        model_id="knowledgator/gliner-bi-large-v2.0",
        device="cuda:0",
    )
    backend.load()

    assert backend.loaded is True
    entities = backend.extract(
        "Use PostgreSQL and Redis.",
        labels=["technology"],
        threshold=0.6,
    )

    assert entities == [
        {"text": "PostgreSQL", "label": "technology", "start": 4, "end": 14, "score": 0.95},
        {"text": "Redis", "label": "technology", "start": 19, "end": 24, "score": 0.91},
    ]
