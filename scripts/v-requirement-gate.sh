#!/usr/bin/env bash
set -euo pipefail

ROOT="${SELFCHECK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
FEATURE="${1:-ecommerce-product-ai-pipeline}"
VERIFY_GROUPS="${2:-static,api,browser,evidence}"
EVENT="${3:-requirement.changed.v.${FEATURE}}"
SOURCE="${SELFCHECK_SOURCE:-local}"
TIMEOUT="${SELFCHECK_TIMEOUT:-300}"
EXECUTOR_COMMAND="${SELFCHECK_EXECUTOR_COMMAND:-}"
ALLOW_PARTIAL="${SELFCHECK_ALLOW_PARTIAL:-0}"

cd "$ROOT"
python3 -m selfcheck validate --root .

# Event/callback entry is useful for causality/latency, but the explicit strict loop below is authoritative.
if python3 -m selfcheck trigger --root . --event "$EVENT" --source "$SOURCE" --timeout "$TIMEOUT"; then
  :
else
  echo "EVENT_TRIGGER_FAILED_OR_UNROUTED: $EVENT; continuing with explicit loop gate" >&2
fi

LOOP_LOG="$(mktemp)"
set +e
python3 -m selfcheck loop --root . --feature "$FEATURE" --groups "$VERIFY_GROUPS" --strict-audit --timeout "$TIMEOUT" | tee "$LOOP_LOG"
LOOP_EXIT=${PIPESTATUS[0]}
set -e

latest_status() {
  python3 - "$FEATURE" <<'PY'
import json, sys
from pathlib import Path
p = Path('reports/loops') / sys.argv[1] / 'latest.json'
print(json.loads(p.read_text()).get('status') if p.exists() else 'MISSING')
PY
}

case "$LOOP_EXIT" in
  0)
    STATUS="$(latest_status)"
    if [[ "$STATUS" == "PASS_WITH_NOTES" && "$ALLOW_PARTIAL" != "1" ]]; then
      echo "V_REQUIREMENT_GATE_PARTIAL_ONLY: $FEATURE status=$STATUS; set SELFCHECK_ALLOW_PARTIAL=1 for partial gates" >&2
      exit 2
    fi
    echo "V_REQUIREMENT_GATE_${STATUS}: $FEATURE"
    exit 0
    ;;
  2)
    echo "V_REQUIREMENT_GATE_NEEDS_REPAIR: $FEATURE" >&2
    DISPATCH_PATH="$(awk '/^DISPATCH: / {print $2}' "$LOOP_LOG" | tail -1)"
    if [[ -n "$EXECUTOR_COMMAND" ]]; then
      if [[ -n "$DISPATCH_PATH" ]]; then
        python3 -m selfcheck dispatch consume --root . --path "$DISPATCH_PATH" --actor orchestrator --executor-command "$EXECUTOR_COMMAND" --executor-timeout "$TIMEOUT" --loop-timeout "$TIMEOUT"
      else
        python3 -m selfcheck dispatch consume --root . --feature "$FEATURE" --actor orchestrator --executor-command "$EXECUTOR_COMMAND" --executor-timeout "$TIMEOUT" --loop-timeout "$TIMEOUT"
      fi
      # Full explicit rerun after repair consumption to catch regressions outside affected dispatch groups.
      python3 -m selfcheck loop --root . --feature "$FEATURE" --groups "$VERIFY_GROUPS" --strict-audit --timeout "$TIMEOUT"
    else
      if [[ -n "$DISPATCH_PATH" ]]; then
        python3 -m selfcheck dispatch plan --root . --path "$DISPATCH_PATH" || true
      else
        python3 -m selfcheck dispatch plan --root . --feature "$FEATURE" || true
      fi
      echo "Set SELFCHECK_EXECUTOR_COMMAND to consume repair dispatch automatically." >&2
      exit 2
    fi
    ;;
  3)
    echo "V_REQUIREMENT_GATE_BLOCKED: $FEATURE" >&2
    python3 -m selfcheck dispatch plan --root . --feature "$FEATURE" || true
    exit 3
    ;;
  *)
    echo "V_REQUIREMENT_GATE_FAIL: $FEATURE exit=$LOOP_EXIT" >&2
    exit "$LOOP_EXIT"
    ;;
esac
