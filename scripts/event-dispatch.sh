#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
EVENT_NAME="${2:?event name required}"
PAYLOAD_FILE="${3:-}"
cd "$ROOT"
if [[ -n "$PAYLOAD_FILE" ]]; then
  python3 -m selfcheck trigger --root . --event "$EVENT_NAME" --payload-file "$PAYLOAD_FILE" --timeout 300
else
  python3 -m selfcheck trigger --root . --event "$EVENT_NAME" --timeout 300
fi
