#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
cd "$ROOT"
python3 -m selfcheck validate --root .
python3 -m selfcheck audit --root .
python3 -m selfcheck run --root . --feature ecommerce-product-ai-pipeline --groups static,api,browser --timeout 300
python3 -m selfcheck audit --root . --feature ecommerce-product-ai-pipeline --strict-missing
