#!/usr/bin/env bash
set -euo pipefail

DATUM_API="${DATUM_API:-http://localhost:8001/api/v1}"
DATUM_API_KEY="${DATUM_API_KEY:-}"

INPUT="$(cat)"
SESSION_ID="$(
  printf '%s' "$INPUT" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("session_id") or "").strip())' 2>/dev/null || true
)"

[ -z "$SESSION_ID" ] && exit 0

curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/flush" \
  -H "X-API-Key: ${DATUM_API_KEY}" \
  >/dev/null 2>&1 || true

curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/finalize" \
  -H "X-API-Key: ${DATUM_API_KEY}" \
  >/dev/null 2>&1 || true
