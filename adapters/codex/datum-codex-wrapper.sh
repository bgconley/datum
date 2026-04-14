#!/usr/bin/env bash
set -euo pipefail

DATUM_API="${DATUM_API:-http://localhost:8001/api/v1}"
DATUM_API_KEY="${DATUM_API_KEY:-}"
DATUM_PROJECT="${DATUM_PROJECT_SLUG:-}"
SESSION_ID="${DATUM_SESSION_ID:-ses_codex_$(date +%s)_$$}"
STRICT_LIFECYCLE="${DATUM_STRICT_LIFECYCLE:-auto}" # auto|0|1

echo "[datum] Starting lifecycle session ${SESSION_ID}..."

curl -sf -X POST "${DATUM_API}/agent/sessions/start" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${DATUM_API_KEY}" \
  -d "{\"session_id\":\"${SESSION_ID}\",\"project_slug\":\"${DATUM_PROJECT}\",\"client_type\":\"codex\"}" \
  >/dev/null 2>&1 || echo "[datum] Warning: could not start lifecycle session"

if [ -n "$DATUM_PROJECT" ]; then
  curl -sf "${DATUM_API}/projects/${DATUM_PROJECT}/context?detail=brief&max_tokens=800" \
    -H "X-API-Key: ${DATUM_API_KEY}" \
    -H "X-Session-ID: ${SESSION_ID}" \
    >/dev/null 2>&1 || echo "[datum] Warning: could not record preflight context read"
else
  echo "[datum] Warning: DATUM_PROJECT_SLUG is not set; no automatic preflight context read was recorded."
fi

ENFORCEMENT_MODE="$(
  curl -sf "${DATUM_API}/agent/sessions/${SESSION_ID}/status" \
    -H "X-API-Key: ${DATUM_API_KEY}" \
    2>/dev/null | python3 -c 'import json,sys; print((json.load(sys.stdin).get("enforcement_mode") or "advisory").strip())' 2>/dev/null || echo "advisory"
)"

is_strict() {
  case "${STRICT_LIFECYCLE}" in
    1|true|TRUE|yes|YES|on|ON)
      return 0
      ;;
    0|false|FALSE|no|NO|off|OFF)
      return 1
      ;;
    *)
      [ "${ENFORCEMENT_MODE}" = "blocking" ]
      ;;
  esac
}

echo "[datum] Session ready. Launching Codex..."

CODEX_EXIT=0
DATUM_SESSION_ID="$SESSION_ID" \
DATUM_API="$DATUM_API" \
DATUM_API_KEY="$DATUM_API_KEY" \
DATUM_PROJECT_SLUG="$DATUM_PROJECT" \
codex "$@" || CODEX_EXIT=$?

echo "[datum] Codex exited with code ${CODEX_EXIT}. Flushing lifecycle session..."

POSTFLIGHT_FAILED=0

if ! curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/flush" \
  -H "X-API-Key: ${DATUM_API_KEY}" \
  >/dev/null 2>&1; then
  echo "[datum] ERROR: could not flush deltas for ${SESSION_ID}"
  if is_strict; then
    POSTFLIGHT_FAILED=1
  fi
fi

if ! curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/finalize" \
  -H "X-API-Key: ${DATUM_API_KEY}" \
  >/dev/null 2>&1; then
  echo "[datum] ERROR: could not finalize session ${SESSION_ID}"
  if is_strict; then
    POSTFLIGHT_FAILED=1
  fi
fi

echo "[datum] Session ${SESSION_ID} complete."

if [ "$POSTFLIGHT_FAILED" -eq 1 ] && [ "$CODEX_EXIT" -eq 0 ]; then
  echo "[datum] Failing wrapper because lifecycle postflight failed in strict mode (${ENFORCEMENT_MODE})."
  exit 65
fi

exit "$CODEX_EXIT"
