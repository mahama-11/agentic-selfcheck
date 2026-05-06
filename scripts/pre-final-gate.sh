#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT"
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
