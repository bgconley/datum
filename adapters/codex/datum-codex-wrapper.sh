#!/usr/bin/env bash
set -euo pipefail

DATUM_API="${DATUM_API:-http://localhost:8001/api/v1}"
DATUM_API_KEY="${DATUM_API_KEY:-}"
DATUM_PROJECT="${DATUM_PROJECT_SLUG:-}"
SESSION_ID="${DATUM_SESSION_ID:-ses_codex_$(date +%s)_$$}"

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

echo "[datum] Session ready. Launching Codex..."

CODEX_EXIT=0
DATUM_SESSION_ID="$SESSION_ID" \
DATUM_API="$DATUM_API" \
DATUM_API_KEY="$DATUM_API_KEY" \
DATUM_PROJECT_SLUG="$DATUM_PROJECT" \
codex "$@" || CODEX_EXIT=$?

echo "[datum] Codex exited with code ${CODEX_EXIT}. Flushing lifecycle session..."

curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/flush" \
  -H "X-API-Key: ${DATUM_API_KEY}" \
  >/dev/null 2>&1 || echo "[datum] Warning: could not flush deltas"

curl -sf -X POST "${DATUM_API}/agent/sessions/${SESSION_ID}/finalize" \
  -H "X-API-Key: ${DATUM_API_KEY}" \
  >/dev/null 2>&1 || echo "[datum] Warning: could not finalize session"

echo "[datum] Session ${SESSION_ID} complete."
exit "$CODEX_EXIT"
