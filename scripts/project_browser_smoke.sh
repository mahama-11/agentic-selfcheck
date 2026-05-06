#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="${1:?project id required}"
FEATURE_ID="${2:?feature id required}"
echo "browser-smoke placeholder: project=${PROJECT_ID} feature=${FEATURE_ID}"
echo "Wire Playwright/browser automation before marking browser verifier PASS."
exit 2
