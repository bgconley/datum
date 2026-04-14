#!/usr/bin/env bash
set -euo pipefail

DATUM_API="${DATUM_API:-http://localhost:8001/api/v1}"
DATUM_API_KEY="${DATUM_API_KEY:-}"

INPUT="$(cat)"
SESSION_ID="$(
  printf '%s' "$INPUT" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("session_id") or "").strip())' 2>/dev/null || true
)"

[ -z "$SESSION_ID" ] && exit 0

STATUS="$(
  curl -sf "${DATUM_API}/agent/sessions/${SESSION_ID}/status" \
    -H "X-API-Key: ${DATUM_API_KEY}" \
    2>/dev/null || echo '{}'
)"

read -r HAS_PREFLIGHT ENFORCEMENT_MODE <<EOF
$(
  printf '%s' "$STATUS" | python3 -c 'import json,sys; data=json.load(sys.stdin); print("yes" if data.get("last_preflight_at") else "no", data.get("enforcement_mode","advisory"))' 2>/dev/null || echo "yes advisory"
)
EOF

if [ "$HAS_PREFLIGHT" = "no" ]; then
  if [ "$ENFORCEMENT_MODE" = "blocking" ]; then
    python3 - <<'PY'
import json
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "No Datum preflight detected. Call get_project_context or search_project_memory before writing."
    }
}))
PY
    exit 0
  fi

  python3 - <<'PY'
import json
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "additionalContext": "WARNING: No Datum preflight detected. Consider calling get_project_context or search_project_memory before writing."
    }
}))
PY
fi

exit 0
