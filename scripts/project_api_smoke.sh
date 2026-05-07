#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID="${1:?project id required}"
FEATURE_ID="${2:?feature id required}"
case "${PROJECT_ID}:${FEATURE_ID}" in
  v-workspace:platform-template-mastering)
    python3 scripts/platform_template_mastering_gate.py --project "$PROJECT_ID" --feature "$FEATURE_ID"
    ;;
  v-workspace:platform-template-media-association)
    python3 scripts/platform_template_media_association_gate.py --project "$PROJECT_ID" --feature "$FEATURE_ID"
    ;;
  v-workspace:platform-ops-visible-baseline)
    python3 scripts/platform_ops_visible_baseline_gate.py --project "$PROJECT_ID" --feature "$FEATURE_ID"
    ;;
  v-workspace:dev-seed-baseline|v-ecommerce-worktree:dev-seed-baseline)
    python3 scripts/v_seed_baseline_gate.py --project "$PROJECT_ID" --feature "$FEATURE_ID"
    ;;
  v-ecommerce-worktree:ecommerce-product-ai-pipeline|v-ecommerce-worktree:selfcheck-runtime-loops|v-ecommerce-worktree:selfcheck-repair-loop|v-ecommerce-worktree:selfcheck-dispatch-runner|v-ecommerce-worktree:selfcheck-dispatch-consume-runner|v-ecommerce-worktree:selfcheck-v-requirement-integration)
    python3 scripts/ecommerce_api_smoke.py --project "$PROJECT_ID" --feature "$FEATURE_ID"
    ;;
  *)
    echo "No API smoke harness registered for project=${PROJECT_ID} feature=${FEATURE_ID}" >&2
    exit 2
    ;;
esac
