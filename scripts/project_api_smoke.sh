#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="${1:?project id required}"
FEATURE_ID="${2:?feature id required}"
echo "api-smoke placeholder: project=${PROJECT_ID} feature=${FEATURE_ID}"
echo "Wire a project-specific smoke implementation before marking API verifier PASS."
exit 2
