#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
cd "$ROOT"
python3 -m selfcheck validate --root .
python3 -m selfcheck trigger --root . --event watchdog.every-2h --source cron --timeout 300
