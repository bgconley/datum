from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _load_gliner_class() -> Any:
    from gliner import GLiNER

    return GLiNER


@dataclass(slots=True)
class GlinerBackend:
    model_id: str
    device: str | None = None
    _model: Any = None

    def load(self) -> None:
        if self._model is not None:
            return

        gliner_cls = _load_gliner_class()
        model = gliner_cls.from_pretrained(self.model_id)
        if self.device and hasattr(model, "to"):
            model = model.to(self.device)
        self._model = model

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def extract(
        self,
        text: str,
        *,
        labels: list[str],
        threshold: float,
    ) -> list[dict[str, Any]]:
        if not text.strip():
            return []
        if self._model is None:
            raise RuntimeError("GLiNER model not loaded")

        predictions = self._model.predict_entities(
            text,
            labels,
            threshold=threshold,
        )
        entities: list[dict[str, Any]] = []
        for item in predictions:
            entities.append(
                {
                    "text": str(item["text"]),
                    "label": str(item["label"]).strip().casefold(),
                    "start": int(item["start"]),
                    "end": int(item["end"]),
                    "score": float(item.get("score", 0.0)),
                }
            )
        return entities
