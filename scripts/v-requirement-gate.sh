#!/usr/bin/env bash
set -euo pipefail
ROOT="${SELFCHECK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
FEATURE="${1:-ecommerce-product-ai-pipeline}"
VERIFY_GROUPS="${2:-static,api,browser,evidence}"
EVENT="${3:-requirement.changed.v.${FEATURE}}"
exec "$ROOT/scripts/requirement-gate.sh" "$FEATURE" "$VERIFY_GROUPS" "$EVENT"
