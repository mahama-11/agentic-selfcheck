#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

CASES = [
    (
        'prep-page-selects-lowlevel-critical-and-style-governance',
        ['ecommerce-frontend/src/pages/production/PrepHubPage.tsx'],
        {'ecommerce-v2-prep-sandbox-lowlevel', 'ecommerce-critical-journey-release-gate', 'ecommerce-frontend-style-governance', 'ecommerce-large-source-locality-guard'},
    ),
    (
        'visualworkflow-selects-lowlevel-and-critical',
        ['ecommerce-backend/internal/modules/visualworkflow/service.go'],
        {'ecommerce-v2-prep-sandbox-lowlevel', 'ecommerce-critical-journey-release-gate', 'ecommerce-large-source-locality-guard'},
    ),
    (
        'platform-runtime-selects-platform-and-critical-gates',
        ['platform-backend/internal/modules/runtime/provider_minimax_image.go'],
        {'platform-core-engineering-baseline', 'platform-runtime-state-machine-baseline', 'platform-runtime-business-integration-safety', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate'},
    ),
    (
        'platform-wallet-selects-financial-business-gate',
        ['platform-backend/internal/modules/wallet/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate'},
    ),
    (
        'platform-metering-selects-financial-business-gate',
        ['platform-backend/internal/modules/metering/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate'},
    ),
    (
        'platform-billing-selects-financial-business-gate',
        ['platform-backend/internal/modules/billing/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate'},
    ),
    (
        'platform-commercial-selects-platform-and-critical-gates',
        ['platform-backend/internal/modules/commercial/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate'},
    ),
    (
        'platform-catalog-selects-financial-business-gate',
        ['platform-backend/internal/modules/catalog/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate'},
    ),
    (
        'platform-incentive-selects-financial-business-gate',
        ['platform-backend/internal/modules/incentive/service.go'],
        {'platform-financial-consistency-baseline', 'platform-financial-business-consistency'},
    ),
    (
        'platform-quota-selects-financial-gate',
        ['platform-backend/internal/modules/quota/service.go'],
        {'platform-financial-consistency-baseline', 'platform-financial-business-consistency'},
    ),
    (
        'platform-control-selects-financial-business-gate',
        ['platform-backend/internal/modules/control/service.go'],
        {'platform-financial-business-consistency'},
    ),
    (
        'platform-frontend-selects-platform-engineering-and-ops-gates',
        ['platform-frontend/src/pages/catalog/CatalogPage.tsx'],
        {'platform-core-engineering-baseline', 'platform-ops-visible-baseline'},
    ),
    (
        'style-token-change-selects-style-governance',
        ['ecommerce-frontend/src/index.css'],
        {'ecommerce-frontend-style-governance', 'ecommerce-large-source-locality-guard'},
    ),
    (
        'acceptance-governance-doc-selects-style-governance',
        ['ecommerce-frontend/docs/acceptance-tdd-governance.md'],
        {'ecommerce-frontend-style-governance', 'ecommerce-large-source-locality-guard'},
    ),
    (
        'acceptance-governance-script-selects-style-governance',
        ['ecommerce-frontend/scripts/ecommerce-acceptance-governance-gate.mjs'],
        {'ecommerce-frontend-style-governance', 'ecommerce-large-source-locality-guard'},
    ),
    (
        'product-scoped-ai-tool-selects-style-governance',
        ['ecommerce-frontend/src/pages/ToolPage.tsx'],
        {'ecommerce-frontend-style-governance', 'ecommerce-large-source-locality-guard'},
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
