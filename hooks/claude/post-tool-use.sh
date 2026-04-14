#!/usr/bin/env bash
set -euo pipefail

DATUM_API="${DATUM_API:-http://localhost:8001/api/v1}"
DATUM_API_KEY="${DATUM_API_KEY:-}"

INPUT="$(cat)"
SESSION_ID="$(
  printf '%s' "$INPUT" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("session_id") or "").strip())' 2>/dev/null || true
)"
[ -z "$SESSION_ID" ] && exit 0

DELTA_JSON="$(
  printf '%s' "$INPUT" | python3 -c '
import json, sys
data = json.load(sys.stdin)
tool = data.get("tool_name", "")
tool_input = data.get("tool_input", {}) or {}

if tool in {"Edit", "Write", "MultiEdit"}:
    path = tool_input.get("file_path") or tool_input.get("path") or "unknown"
    payload = {"delta_type": "file_touch", "detail": {"path": path, "action": "modify"}}
elif tool == "Bash":
    command = (tool_input.get("command") or "")[:200]
    payload = {"delta_type": "command_run", "detail": {"command": command}}
else:
    raise SystemExit(0)

print(json.dumps(payload))
' 2>/dev/null || true
)"

[ -z "$DELTA_JSON" ] && exit 0

curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/delta" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${DATUM_API_KEY}" \
  -d "$DELTA_JSON" \
  >/dev/null 2>&1 || true
