#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def run(root: Path, target: Path, *extra: str) -> dict:
    cmd = [str(root / 'scripts/platform_core_engineering_baseline.py'), '--target-root', str(target), '--report', str(target / 'report.json'), '--format', 'json', *extra]
    cp = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    try:
        payload = json.loads(cp.stdout)
    except Exception:
        payload = {}
    return {'returncode': cp.returncode, 'payload': payload, 'stdout': cp.stdout[-2000:], 'stderr': cp.stderr[-2000:]}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    cases = []
    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/modules/runtime/service.go', '''package runtime
func ok() { transitionRuntimeState("queued", "running") }
''')
        write(target / 'platform-backend/internal/router/routes.go', '''package router
func r(g Group) { g.GET("/api/v1/runtime/jobs", h) }
''')
        write(target / 'platform-backend/docs/INTERNAL_API_CONTRACT.md', '''# Internal API Contract

GET /api/v1/runtime/jobs lists runtime jobs.
- Handler: h
- Request: query filters only.
- Response: success envelope with data list.
''')
        ok_case = run(root, target, '--changed-file', 'platform-backend/internal/router/routes.go')
        cases.append({'case': 'route-change-with-contract-reference-passes', 'ok': ok_case['returncode'] == 0 and ok_case['payload'].get('status') == 'PASS', **ok_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/router/routes.go', '''package router
func r(g Group) { g.POST("/api/v1/runtime/jobs", h) }
''')
        write(target / 'platform-backend/docs/INTERNAL_API_CONTRACT.md', '''# Internal API Contract

GET /api/v1/runtime/jobs lists runtime jobs.
''')
        method_mismatch_case = run(root, target, '--changed-file', 'platform-backend/internal/router/routes.go')
        scanners = {f.get('scanner') for f in method_mismatch_case['payload'].get('findings', [])}
        cases.append({'case': 'route-method-mismatch-fails-closed', 'ok': method_mismatch_case['returncode'] != 0 and method_mismatch_case['payload'].get('status') == 'NEEDS_REPAIR' and 'route_openapi_drift_check' in scanners, **method_mismatch_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/router/routes.go', '''package router
func r(g Group) { g.POST("/api/v1/runtime/jobs", h) }
''')
        write(target / 'platform-backend/docs/openapi.yaml', '''openapi: 3.0.0
paths:
  /api/v1/runtime/jobs:
    post:
      summary: create runtime job
      x-handler: h
      requestBody:
        description: create runtime job request
      responses:
        '200':
          description: success envelope response
''')
        openapi_case = run(root, target, '--changed-file', 'platform-backend/internal/router/routes.go')
        cases.append({'case': 'route-openapi-method-reference-passes', 'ok': openapi_case['returncode'] == 0 and openapi_case['payload'].get('status') == 'PASS', **openapi_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/router/routes.go', '''package router
func r(router Group) {
  v1 := router.Group("/api/v1")
  auth := v1.Group("/auth")
  auth.POST("/register", authHandler.Register)
}
''')
        write(target / 'platform-backend/docs/openapi.yaml', '''openapi: 3.0.0
paths:
  /api/v1/auth/register:
    post:
      summary: register account
      x-handler: Register
      requestBody:
        description: register request body
      responses:
        '200':
          description: success response envelope
''')
        nested_case = run(root, target)
        stats = nested_case['payload'].get('stats', {})
        cases.append({'case': 'nested-gin-groups-compose-full-route-with-clean-checkout', 'ok': nested_case['returncode'] == 0 and nested_case['payload'].get('status') == 'PASS' and stats.get('route_openapi_checked_signatures') == 1, **nested_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/router/routes.go', '''package router
func r(g Group) { g.POST("/api/v1/runtime/jobs", runtimeHandler.CreateJob) }
''')
        write(target / 'platform-backend/docs/INTERNAL_API_CONTRACT.md', '''# Internal API Contract

POST /api/v1/runtime/jobs creates runtime jobs.
''')
        path_only_case = run(root, target, '--changed-file', 'platform-backend/internal/router/routes.go')
        messages = '\n'.join(str(f.get('message', '')) for f in path_only_case['payload'].get('findings', []))
        cases.append({'case': 'route-method-path-only-evidence-fails-semantic-diff', 'ok': path_only_case['returncode'] != 0 and path_only_case['payload'].get('status') == 'NEEDS_REPAIR' and 'only method/path evidence' in messages, **path_only_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/router/routes.go', '''package router
func r(g Group) { g.POST("/api/v1/runtime/jobs", runtimeHandler.CreateJob) }
''')
        write(target / 'platform-backend/docs/INTERNAL_API_CONTRACT.md', '''# Internal API Contract

POST /api/v1/runtime/jobs creates runtime jobs.
- Request: Runtime job create body.
- Response: success envelope with runtime job data.
''')
        missing_handler_case = run(root, target, '--changed-file', 'platform-backend/internal/router/routes.go')
        messages = '\n'.join(str(f.get('message', '')) for f in missing_handler_case['payload'].get('findings', []))
        cases.append({'case': 'route-named-handler-missing-from-contract-fails', 'ok': missing_handler_case['returncode'] != 0 and missing_handler_case['payload'].get('status') == 'NEEDS_REPAIR' and 'does not name that handler' in messages, **missing_handler_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/router/routes.go', '''package router
func r(g Group) { g.GET("/api/v1/runtime/jobs", func(c Context) {}) }
''')
        write(target / 'platform-backend/docs/INTERNAL_API_CONTRACT.md', '''# Internal API Contract

GET /api/v1/runtime/jobs lists runtime jobs.
- Request: query filters only.
- Response: success envelope with data list.
''')
        inline_handler_case = run(root, target, '--changed-file', 'platform-backend/internal/router/routes.go')
        messages = '\n'.join(str(f.get('message', '')) for f in inline_handler_case['payload'].get('findings', []))
        cases.append({'case': 'route-inline-handler-is-pass-with-notes-not-false-fail', 'ok': inline_handler_case['returncode'] == 0 and inline_handler_case['payload'].get('status') == 'PASS_WITH_NOTES' and 'inline handler evidence' in messages, **inline_handler_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/router/routes.go', '''package router
func r(g Group) { g.POST("/api/v1/runtime/jobs/:jobID/retry", h) }
''')
        write(target / 'platform-backend/docs/INTERNAL_API_CONTRACT.md', '''# Internal API Contract

GET /api/v1/runtime/jobs lists runtime jobs.
''')
        drift_case = run(root, target, '--changed-file', 'platform-backend/internal/router/routes.go')
        scanners = {f.get('scanner') for f in drift_case['payload'].get('findings', [])}
        cases.append({'case': 'route-change-without-contract-reference-fails-closed', 'ok': drift_case['returncode'] != 0 and drift_case['payload'].get('status') == 'NEEDS_REPAIR' and 'route_openapi_drift_check' in scanners, **drift_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/modules/runtime/service.go', '''package runtime
func bad(db DB, key string) {
  db.Model(&Job{}).Update("status", "done")
  _ = key // Idempotency-Key
  db.Exec("UPDATE jobs SET status = 'done'")
}
''')
        bad_case = run(root, target)
        scanners = {f.get('scanner') for f in bad_case['payload'].get('findings', [])}
        cases.append({'case': 'severe-findings-fail-closed', 'ok': bad_case['returncode'] != 0 and {'raw_status_write_scanner', 'unscoped_idempotency_scanner', 'service_raw_db_expansion_scanner'}.issubset(scanners), **bad_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/modules/wallet/service.go', '''package wallet
func product() string { return "ecommerce" }
''')
        product_case = run(root, target)
        scanners = {f.get('scanner') for f in product_case['payload'].get('findings', [])}
        messages = '\n'.join(str(f.get('message', '')) for f in product_case['payload'].get('findings', []))
        cases.append({'case': 'unclassified-production-product-literal-fails-closed', 'ok': product_case['returncode'] != 0 and product_case['payload'].get('status') == 'NEEDS_REPAIR' and 'product_hardcode_classifier' in scanners and 'classification=unclassified' in messages, **product_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/modules/runtime/service.go', '''package runtime
func ok() { transitionRuntimeState("queued", "running") }
''')
        runtime_case = run(root, target, '--profile', 'runtime')
        cases.append({'case': 'runtime-profile-produces-report', 'ok': runtime_case['returncode'] == 0 and runtime_case['payload'].get('feature') == 'platform-runtime-state-machine-baseline' and runtime_case['payload'].get('profile') == 'runtime', **runtime_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/modules/wallet/service.go', '''package wallet
func ok() string { return "wallet" }
''')
        financial_case = run(root, target, '--profile', 'financial')
        cases.append({'case': 'financial-profile-produces-report', 'ok': financial_case['returncode'] == 0 and financial_case['payload'].get('feature') == 'platform-financial-consistency-baseline' and financial_case['payload'].get('profile') == 'financial', **financial_case})

    with tempfile.TemporaryDirectory() as td:
        target = Path(td)
        write(target / 'platform-backend/internal/modules/quota/service.go', '''package quota
func bad(db DB) { db.Exec("UPDATE quotas SET status = 'exhausted'") }
''')
        quota_case = run(root, target, '--profile', 'financial')
        scanners = {f.get('scanner') for f in quota_case['payload'].get('findings', [])}
        files_scanned = quota_case['payload'].get('files_scanned')
        cases.append({'case': 'financial-profile-scans-quota-severe-finding', 'ok': quota_case['returncode'] != 0 and quota_case['payload'].get('profile') == 'financial' and files_scanned == 1 and 'service_raw_db_expansion_scanner' in scanners, **quota_case})

    ok = all(case['ok'] for case in cases)
    print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'cases': cases}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
