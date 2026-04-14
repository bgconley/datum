# Datum model-service systemd units

These units supervise the native Datum inference services on the GPU node.

## Runtime assumptions

- Repo checkout: `/tank/repos/datum`
- Embedder/reranker venv: `/tank/venvs/datum-model-services`
- GLiNER venv: `/tank/venvs/datum-gliner`
- User: `bgconley`
- Journald is the primary log sink

## Install

```bash
sudo cp systemd/datum-embedder.service /etc/systemd/system/
sudo cp systemd/datum-reranker.service /etc/systemd/system/
sudo cp systemd/gliner-ner.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable datum-embedder datum-reranker gliner-ner
sudo systemctl start datum-embedder datum-reranker gliner-ner
```

## Health checks

```bash
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:8011/health
curl http://127.0.0.1:8012/health
systemctl status datum-embedder datum-reranker gliner-ner
journalctl -u datum-embedder -u datum-reranker -u gliner-ner -f
```

## Notes

- The embedder and reranker intentionally share the dedicated Datum model-services venv.
- GLiNER stays in its own venv to avoid drifting the embedder/reranker dependency graph.
- If GPU placement changes, adjust `CUDA_VISIBLE_DEVICES` and the service-local device variables together.
