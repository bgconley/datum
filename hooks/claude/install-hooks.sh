#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATUM_API="${1:-http://localhost:8001/api/v1}"
PROJECT_SLUG="${2:-}"

cat <<EOF
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume|clear|compact",
        "hooks": [
          {
            "type": "command",
            "command": "DATUM_API='${DATUM_API}' DATUM_PROJECT_SLUG='${PROJECT_SLUG}' bash '${SCRIPT_DIR}/session-start.sh'"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "DATUM_API='${DATUM_API}' bash '${SCRIPT_DIR}/pre-tool-use.sh'"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|Bash",
        "hooks": [
          {
            "type": "command",
            "command": "DATUM_API='${DATUM_API}' bash '${SCRIPT_DIR}/post-tool-use.sh'"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "DATUM_API='${DATUM_API}' bash '${SCRIPT_DIR}/pre-compact.sh'"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "DATUM_API='${DATUM_API}' bash '${SCRIPT_DIR}/stop.sh'"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "DATUM_API='${DATUM_API}' bash '${SCRIPT_DIR}/session-end.sh'"
          }
        ]
      }
    ]
  }
}
EOF
