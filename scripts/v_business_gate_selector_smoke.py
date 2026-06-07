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
        {'platform-core-engineering-baseline', 'platform-runtime-state-machine-baseline', 'platform-runtime-business-integration-safety', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate', 'platform-stability-closed-loop-gates'},
    ),
    (
        'platform-wallet-selects-financial-business-gate',
        ['platform-backend/internal/modules/wallet/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate', 'platform-stability-closed-loop-gates'},
    ),
    (
        'platform-metering-selects-financial-business-gate',
        ['platform-backend/internal/modules/metering/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate', 'platform-stability-closed-loop-gates'},
    ),
    (
        'platform-billing-selects-financial-business-gate',
        ['platform-backend/internal/modules/billing/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate', 'platform-stability-closed-loop-gates'},
    ),
    (
        'platform-commercial-selects-platform-and-critical-gates',
        ['platform-backend/internal/modules/commercial/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate', 'platform-stability-closed-loop-gates'},
    ),
    (
        'platform-catalog-selects-financial-business-gate',
        ['platform-backend/internal/modules/catalog/service.go'],
        {'platform-core-engineering-baseline', 'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-ops-visible-baseline', 'ecommerce-critical-journey-release-gate', 'platform-stability-closed-loop-gates'},
    ),
    (
        'platform-incentive-selects-financial-business-gate',
        ['platform-backend/internal/modules/incentive/service.go'],
        {'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-stability-closed-loop-gates'},
    ),
    (
        'platform-quota-selects-financial-gate',
        ['platform-backend/internal/modules/quota/service.go'],
        {'platform-financial-consistency-baseline', 'platform-financial-business-consistency', 'platform-stability-closed-loop-gates'},
    ),
    (
        'platform-control-selects-financial-business-gate',
        ['platform-backend/internal/modules/control/service.go'],
        {'platform-financial-business-consistency', 'platform-stability-closed-loop-gates'},
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
        'platform-openapi-change-selects-contract-gates',
        ['platform-backend/docs/openapi/platform.yaml'],
        {'platform-core-engineering-baseline', 'platform-stability-closed-loop-gates', 'v-platform-contract-evidence-bridge'},
    ),
    (
        'ecommerce-frontend-type-change-selects-consumer-gates',
        ['ecommerce-frontend/src/types/product.ts'],
        {'ecommerce-critical-journey-release-gate', 'ecommerce-v1-listing-export-gate', 'ecommerce-large-source-locality-guard'},
    ),
    (
        'deploy-script-change-selects-release-gates',
        ['tools/dev/deploy-cloud-dev-all.sh'],
        {'ecommerce-critical-journey-release-gate', 'platform-stability-closed-loop-gates'},
    ),
    (
        'menu-platform-compatibility-change-selects-platform-ops-gate',
        ['menu-backend/internal/modules/studio/service.go'],
        {'platform-ops-visible-baseline', 'v-ai-native-governance-foundation', 'v-menu-contract-evidence-bridge', 'menu-critical-journey-gates'},
    ),
    (
        'menu-selfcheck-artifact-change-selects-menu-gates',
        ['features/menu-critical-journey-gates.yaml', 'scripts/v_menu_critical_journey_gates_smoke.py'],
        {'v-menu-contract-evidence-bridge', 'menu-critical-journey-gates'},
    ),
    (
        'unrelated-doc-selects-no-business-gate',
        ['docs/random-note.md'],
        set(),
    ),
]


def run_case(root: Path, name: str, files: list[str], expected: set[str], expected_status: str = 'PASS') -> dict:
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
    status = (payload or {}).get('status')
    ok_return = (cp.returncode == 0) if expected_status == 'PASS' else (cp.returncode != 0)
    ok = ok_return and status == expected_status and selected == expected
    return {
        'case': name,
        'changed_files': files,
        'expected': sorted(expected),
        'actual': sorted(selected),
        'returncode': cp.returncode,
        'status': status,
        'expected_status': expected_status,
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
