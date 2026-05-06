#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
FEATURE="${2:-selfcheck-runtime-loops}"
VERIFY_GROUPS="${3:-static,api,browser,evidence}"
cd "$ROOT"
python3 -m selfcheck validate --root .
python3 -m selfcheck run --root . --feature "$FEATURE" --groups "$VERIFY_GROUPS" --timeout 300
python3 -m selfcheck audit --root . --feature "$FEATURE" --strict-missing
