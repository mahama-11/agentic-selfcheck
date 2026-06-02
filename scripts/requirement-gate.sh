#!/usr/bin/env bash
set -euo pipefail
ROOT="${SELFCHECK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
FEATURE="${1:?usage: scripts/requirement-gate.sh <feature> [groups] [event]}"
VERIFY_GROUPS="${2:-static,api,browser,evidence}"
EVENT="${3:-requirement.changed.${FEATURE}}"
SOURCE="${SELFCHECK_SOURCE:-local}"
TIMEOUT="${SELFCHECK_TIMEOUT:-300}"
EXECUTOR_COMMAND="${SELFCHECK_EXECUTOR_COMMAND:-}"
ENABLE_REPAIR="${SELFCHECK_ENABLE_REPAIR:-0}"
ALLOW_PARTIAL="${SELFCHECK_ALLOW_PARTIAL:-0}"

cd "$ROOT"
python3 -m selfcheck validate --root .

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
      echo "REQUIREMENT_GATE_PARTIAL_ONLY: $FEATURE status=$STATUS; set SELFCHECK_ALLOW_PARTIAL=1 for partial gates" >&2
      exit 2
    fi
    echo "REQUIREMENT_GATE_${STATUS}: $FEATURE"
    exit 0
    ;;
  2)
    echo "REQUIREMENT_GATE_NEEDS_REPAIR: $FEATURE" >&2
    FAILURE_LOOP_REPORT="reports/loops/$FEATURE/latest.json"
    if [[ -f "$FAILURE_LOOP_REPORT" ]]; then
      python3 scripts/v_failure_closed_loop.py ingest --root . --report "$FAILURE_LOOP_REPORT" --source requirement-gate --format text >&2 || true
    fi
    DISPATCH_PATH="$(awk '/^DISPATCH: / {print $2}' "$LOOP_LOG" | tail -1)"
    if [[ -n "$EXECUTOR_COMMAND" && "$ENABLE_REPAIR" == "1" ]]; then
      if [[ -n "$DISPATCH_PATH" ]]; then
        python3 -m selfcheck dispatch consume --root . --path "$DISPATCH_PATH" --actor orchestrator --executor-command "$EXECUTOR_COMMAND" --executor-timeout "$TIMEOUT" --loop-timeout "$TIMEOUT"
      else
        python3 -m selfcheck dispatch consume --root . --feature "$FEATURE" --actor orchestrator --executor-command "$EXECUTOR_COMMAND" --executor-timeout "$TIMEOUT" --loop-timeout "$TIMEOUT"
      fi
      python3 -m selfcheck loop --root . --feature "$FEATURE" --groups "$VERIFY_GROUPS" --strict-audit --timeout "$TIMEOUT"
    else
      if [[ -n "$DISPATCH_PATH" ]]; then
        python3 -m selfcheck dispatch plan --root . --path "$DISPATCH_PATH" || true
      else
        python3 -m selfcheck dispatch plan --root . --feature "$FEATURE" || true
      fi
      echo "Set SELFCHECK_ENABLE_REPAIR=1 and SELFCHECK_EXECUTOR_COMMAND to consume repair dispatch automatically from an explicit repair runner." >&2
      exit 2
    fi
    ;;
  3)
    echo "REQUIREMENT_GATE_BLOCKED: $FEATURE" >&2
    FAILURE_LOOP_REPORT="reports/loops/$FEATURE/latest.json"
    if [[ -f "$FAILURE_LOOP_REPORT" ]]; then
      python3 scripts/v_failure_closed_loop.py ingest --root . --report "$FAILURE_LOOP_REPORT" --source requirement-gate-blocked --format text >&2 || true
    fi
    python3 -m selfcheck dispatch plan --root . --feature "$FEATURE" || true
    exit 3
    ;;
  *)
    echo "REQUIREMENT_GATE_FAIL: $FEATURE exit=$LOOP_EXIT" >&2
    exit "$LOOP_EXIT"
    ;;
esac
