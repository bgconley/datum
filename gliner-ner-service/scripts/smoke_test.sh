#!/usr/bin/env bash
set -euo pipefail

curl -fsS http://127.0.0.1:8012/health
curl -fsS http://127.0.0.1:8012/extract \
  -H 'Content-Type: application/json' \
  -d '{"text":"Use PostgreSQL and Redis.","labels":["technology"],"threshold":0.5}'
