#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="${1:?project id required}"
FEATURE_ID="${2:?feature id required}"
case "${PROJECT_ID}:${FEATURE_ID}" in
  v-ecommerce-worktree:ecommerce-product-ai-pipeline|v-ecommerce-worktree:selfcheck-runtime-loops|v-ecommerce-worktree:selfcheck-repair-loop|v-ecommerce-worktree:selfcheck-dispatch-runner|v-ecommerce-worktree:selfcheck-dispatch-consume-runner|v-ecommerce-worktree:selfcheck-v-requirement-integration)
    python3 scripts/ecommerce_api_smoke.py --project "$PROJECT_ID" --feature "$FEATURE_ID"
    ;;
  *)
    echo "No API smoke harness registered for project=${PROJECT_ID} feature=${FEATURE_ID}" >&2
    exit 2
    ;;
esac
