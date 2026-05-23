#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

CASES = [
    (
        'prep-page-selects-lowlevel-and-critical',
        ['ecommerce-frontend/src/pages/production/PrepHubPage.tsx'],
        {'ecommerce-v2-prep-sandbox-lowlevel', 'ecommerce-critical-journey-release-gate'},
    ),
    (
        'visualworkflow-selects-lowlevel-and-critical',
        ['ecommerce-backend/internal/modules/visualworkflow/service.go'],
        {'ecommerce-v2-prep-sandbox-lowlevel', 'ecommerce-critical-journey-release-gate'},
    ),
    (
        'platform-runtime-selects-platform-and-critical-gates',
        ['platform-backend/internal/modules/runtime/provider_minimax_image.go'],
        {'platform-core-engineering-baseline', 'platform-runtime-state-machine-baseline', 'platform-runtime-business-integration-safety', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate'},
    ),
    (
        'platform-commercial-selects-platform-and-critical-gates',
        ['platform-backend/internal/modules/commercial/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate'},
    ),
    (
        'platform-quota-selects-financial-gate',
        ['platform-backend/internal/modules/quota/service.go'],
        {'platform-financial-consistency-baseline'},
    ),
    (
        'platform-frontend-selects-platform-engineering-and-ops-gates',
        ['platform-frontend/src/pages/catalog/CatalogPage.tsx'],
        {'platform-core-engineering-baseline', 'platform-ops-visible-baseline'},
    ),
    (
        'unrelated-doc-selects-no-business-gate',
        ['docs/random-note.md'],
        set(),
    ),
]


def run_case(root: Path, name: str, files: list[str], expected: set[str]) -> dict:
    cmd = ['scripts/v_business_gate_selector.py', '--root', str(root), '--format', 'json']
    for file in files:
        cmd.extend(['--changed-file', file])
    cp = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    payload = None
    try:
        payload = json.loads(cp.stdout)
    except Exception:
        payload = None
    selected = {str(g.get('feature')) for g in (payload or {}).get('selected_gates', []) if isinstance(g, dict) and g.get('feature')}
    ok = cp.returncode == 0 and selected == expected
    return {
        'case': name,
        'changed_files': files,
        'expected': sorted(expected),
        'actual': sorted(selected),
        'returncode': cp.returncode,
        'ok': ok,
        'stdout': cp.stdout[-2000:],
        'stderr': cp.stderr[-2000:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json', 'text'], default='json')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    cases = [run_case(root, *case) for case in CASES]
    ok = all(case['ok'] for case in cases)
    payload = {'status': 'PASS' if ok else 'FAIL', 'cases': cases}
    if args.format == 'json':
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print('status=' + payload['status'])
        for case in cases:
            print(f"{case['case']}: expected={case['expected']} actual={case['actual']}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
