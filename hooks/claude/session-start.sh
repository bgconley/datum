#!/usr/bin/env bash
set -euo pipefail

DATUM_API="${DATUM_API:-http://localhost:8001/api/v1}"
DATUM_API_KEY="${DATUM_API_KEY:-}"
DATUM_PROJECT="${DATUM_PROJECT_SLUG:-}"

INPUT="$(cat)"
SESSION_ID="$(
  printf '%s' "$INPUT" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("session_id") or "").strip())' 2>/dev/null || true
)"

if [ -z "$SESSION_ID" ]; then
  SESSION_ID="ses_$(date +%s)_$$"
fi

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  {
    echo "export DATUM_SESSION_ID='${SESSION_ID}'"
    echo "export DATUM_API='${DATUM_API}'"
    echo "export DATUM_API_KEY='${DATUM_API_KEY}'"
    echo "export DATUM_PROJECT_SLUG='${DATUM_PROJECT}'"
  } >>"$CLAUDE_ENV_FILE"
fi

curl -sf -X POST "${DATUM_API}/agent/sessions/start" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${DATUM_API_KEY}" \
  -d "{\"session_id\":\"${SESSION_ID}\",\"project_slug\":\"${DATUM_PROJECT}\",\"client_type\":\"claude_code\"}" \
  >/dev/null 2>&1 || true

cat <<EOF
Datum session established: ${SESSION_ID}
Project: ${DATUM_PROJECT:-not set}
Rule: Read Datum with get_project_context, search_project_memory, or list_candidates before your first durable write.
Pass session_id="${SESSION_ID}" to all Datum MCP tool calls and preserve it for all Datum API writes.
EOF
