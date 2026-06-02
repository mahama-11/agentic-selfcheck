#!/usr/bin/env bash
set -euo pipefail
cd /root/work/v/ecommerce-backend
exec go test ./internal/modules/visualworkflow ./internal/app
