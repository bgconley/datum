#!/usr/bin/env bash
set -euo pipefail

DATUM_API="${DATUM_API:-http://localhost:8001/api/v1}"
DATUM_API_KEY="${DATUM_API_KEY:-}"

INPUT="$(cat)"
SESSION_ID="$(
  printf '%s' "$INPUT" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("session_id") or "").strip())' 2>/dev/null || true
)"
[ -z "$SESSION_ID" ] && exit 0

STOP_HOOK_ACTIVE="$(
  printf '%s' "$INPUT" | python3 -c 'import json,sys; print(bool(json.load(sys.stdin).get("stop_hook_active", False)))' 2>/dev/null || echo "False"
)"

if [ "$STOP_HOOK_ACTIVE" = "True" ]; then
  curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/flush" \
    -H "X-API-Key: ${DATUM_API_KEY}" \
    >/dev/null 2>&1 || true
  curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/finalize" \
    -H "X-API-Key: ${DATUM_API_KEY}" \
    >/dev/null 2>&1 || true
  exit 0
fi

STATUS="$(
  curl -sf "${DATUM_API}/agent/sessions/${SESSION_ID}/status" \
    -H "X-API-Key: ${DATUM_API_KEY}" \
    2>/dev/null || echo '{}'
)"

read -r IS_DIRTY UNFLUSHED ENFORCEMENT_MODE <<EOF
$(
  printf '%s' "$STATUS" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(bool(data.get("is_dirty", False)), int(data.get("unflushed_delta_count", 0)), data.get("enforcement_mode","advisory"))'
)
EOF

if [ "$IS_DIRTY" = "True" ] || [ "${UNFLUSHED:-0}" -gt 0 ] 2>/dev/null; then
  if [ "$ENFORCEMENT_MODE" = "blocking" ]; then
    python3 - <<PY
import json
print(json.dumps({
    "decision": "block",
    "reason": "Session has ${UNFLUSHED} unflushed deltas. Call flush_deltas or append_session_notes before stopping."
}))
PY
    exit 0
  fi

  curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/flush" \
    -H "X-API-Key: ${DATUM_API_KEY}" \
    >/dev/null 2>&1 || true
fi

curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/finalize" \
  -H "X-API-Key: ${DATUM_API_KEY}" \
  >/dev/null 2>&1 || true
