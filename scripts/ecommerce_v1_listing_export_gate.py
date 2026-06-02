#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

BACKEND_REQUIRED = [
    'internal/migration/migration.go',
    'internal/models/productcenter.go',
    'internal/modules/imageruntime/service.go',
    'internal/modules/productcore/service.go',
    'internal/modules/productcore/handler.go',
    'internal/repository/productcenter_repository.go',
]
FRONTEND_REQUIRED = [
    'src/pages/product/ProductDetailPage.tsx',
    'src/services/imageRuntime.ts',
    'src/services/product.ts',
    'src/types/product.ts',
]


def git_status(repo: Path) -> list[str]:
    cp = subprocess.run(['git', '-C', str(repo), 'status', '--short'], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    if cp.returncode != 0:
        raise RuntimeError(cp.stdout.strip())
    return [line.strip() for line in cp.stdout.splitlines() if line.strip()]


def exists_all(root: Path, paths: list[str]) -> list[str]:
    return [p for p in paths if not (root / p).exists()]


def main() -> int:
    parser = argparse.ArgumentParser(description='Quarantine/readiness gate for Ecommerce V1 listing/export active worktree slice.')
    parser.add_argument('--backend-root', default='/root/work/v/ecommerce-backend')
    parser.add_argument('--frontend-root', default='/root/work/v/ecommerce-frontend')
    parser.add_argument('--format', choices=['json', 'text'], default='json')
    args = parser.parse_args()
    backend = Path(args.backend_root)
    frontend = Path(args.frontend_root)
    findings: list[dict[str, Any]] = []
    if not backend.exists():
        findings.append({'severity': 'error', 'code': 'BACKEND_ROOT_MISSING', 'path': str(backend)})
    if not frontend.exists():
        findings.append({'severity': 'error', 'code': 'FRONTEND_ROOT_MISSING', 'path': str(frontend)})
    if findings:
        status = 'FAIL'
    else:
        for p in exists_all(backend, BACKEND_REQUIRED):
            findings.append({'severity': 'error', 'code': 'BACKEND_REQUIRED_FILE_MISSING', 'path': p})
        for p in exists_all(frontend, FRONTEND_REQUIRED):
            findings.append({'severity': 'error', 'code': 'FRONTEND_REQUIRED_FILE_MISSING', 'path': p})
        backend_status = git_status(backend)
        frontend_status = git_status(frontend)
        pnpm_drift = [line for line in frontend_status if line.endswith('pnpm-lock.yaml')]
        if pnpm_drift:
            findings.append({'severity': 'warning', 'code': 'PACKAGE_MANAGER_LOCK_DRIFT_REQUIRES_OWNER_DECISION_BEFORE_MERGE', 'detail': pnpm_drift})
        status = 'PASS_WITH_NOTES' if findings else 'PASS'
        if any(f['severity'] == 'error' for f in findings):
            status = 'FAIL'
    payload = {
        'status': status,
        'backend_root': str(backend),
        'frontend_root': str(frontend),
        'backend_dirty_count': len(git_status(backend)) if backend.exists() else None,
        'frontend_dirty_count': len(git_status(frontend)) if frontend.exists() else None,
        'merge_state': 'HITL_BLOCKED_WITH_CANONICAL_GATE_EVIDENCE',
        'required_next_checks': [
            'backend productcore/imageruntime/migration/templatecenter tests in same run',
            'frontend typecheck/build in same run',
            'immutable listing version semantics evidence',
            'export/download compatibility evidence',
        ],
        'findings': findings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.format == 'json' else payload)
    return 0 if status != 'FAIL' else 1


if __name__ == '__main__':
    raise SystemExit(main())
