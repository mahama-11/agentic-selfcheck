#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CATEGORY_META = {
    'A_KEEP_CONTROL_PLANE_DOCS': {
        'decision': 'keep',
        'reason': 'Documents the P0/P1 control-plane stabilization and cron responsibility boundaries.',
    },
    'A_KEEP_CORE_CONTRACTS': {
        'decision': 'keep',
        'reason': 'SelfCheck feature/verifier contracts for selector, watchdog, failure loop, and status projection.',
    },
    'A_KEEP_CORE_CONTROL_PLANE': {
        'decision': 'keep',
        'reason': 'Core scripts for business gate selection, working-tree watchdog, failure closed-loop, and status projection.',
    },
    'A_KEEP_CORE_SELECTOR': {
        'decision': 'keep',
        'reason': 'Changed-file to business-gate selector configuration.',
    },
    'A_KEEP_TRIGGER_INTEGRATION': {
        'decision': 'keep-after-review',
        'reason': 'Hook/trigger/requirement-gate integration points that activate the control-plane loop.',
    },
    'B_REVIEW_ECOMMERCE_GATES': {
        'decision': 'review-batch',
        'reason': 'Ecommerce gate contracts and journey adapters should land as a separate reviewed batch.',
    },
    'B_REVIEW_FRONTEND_GOVERNANCE': {
        'decision': 'review-batch',
        'reason': 'Frontend workflow/governance changes are broad and should not be mixed with P0 control-plane stabilization.',
    },
    'B_REVIEW_CROSSPLANET': {
        'decision': 'review-batch',
        'reason': 'Crossplanet/List strategy gates are product-specific and should land separately.',
    },
    'B_REVIEW_SUPPORTING_CHANGES': {
        'decision': 'review-batch',
        'reason': 'Supporting framework/docs changes need per-file review before inclusion.',
    },
    'C_GENERATED_WORKFLOW_EVIDENCE': {
        'decision': 'do-not-commit-by-default',
        'reason': 'Generated workflow evidence; keep as evidence locally unless deliberately promoting canonical workflow fixtures.',
    },
    'C_SESSION_PLAN_CACHE': {
        'decision': 'do-not-commit-by-default',
        'reason': 'Session-local planning cache.',
    },
    'C_GENERATED_REPORTS': {
        'decision': 'do-not-commit-by-default',
        'reason': 'Generated reports are ignored by git and should remain evidence artifacts.',
    },
    'D_UNKNOWN_REVIEW_BEFORE_ACTION': {
        'decision': 'manual-review-required',
        'reason': 'Path does not match known stabilization categories.',
    },
}


def run(argv: list[str], cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def classify(path: str) -> str:
    if path.startswith('.hermes/workflows/'):
        return 'C_GENERATED_WORKFLOW_EVIDENCE'
    if path.startswith('.hermes/plans/'):
        return 'C_SESSION_PLAN_CACHE'
    if path.startswith('reports/'):
        return 'C_GENERATED_REPORTS'
    if path == 'config/v-business-gate-selector.yaml':
        return 'A_KEEP_CORE_SELECTOR'
    if path.startswith(('scripts/v_business_gate_selector', 'scripts/v_working_tree_governance_watchdog', 'scripts/v_failure_closed_loop', 'scripts/v_control_plane_status', 'scripts/v_control_plane_dirty_inventory')):
        return 'A_KEEP_CORE_CONTROL_PLANE'
    if path in {'scripts/v-requirement-gate.sh', 'scripts/requirement-gate.sh', 'scripts/v_continuous_governance_trigger.py', 'scripts/install_v_continuous_governance_hooks.py'}:
        return 'A_KEEP_TRIGGER_INTEGRATION'
    if path.startswith(('features/v-business-gate-selector', 'features/v-working-tree-governance-watchdog', 'features/v-failure-closed-loop', 'features/v-control-plane-status', 'verifiers/v-business-gate-selector', 'verifiers/v-working-tree-governance-watchdog', 'verifiers/v-failure-closed-loop', 'verifiers/v-control-plane-status')):
        return 'A_KEEP_CORE_CONTRACTS'
    if path.startswith(('docs/plans/2026-05-22-', 'docs/v-cron-governance-responsibility-map.md', 'docs/control-plane-dirty-tree-inventory.md')):
        return 'A_KEEP_CONTROL_PLANE_DOCS'
    if path.startswith(('features/ecommerce-', 'verifiers/ecommerce-', 'journeys/', 'schemas/critical-journey', 'scripts/critical_journey', 'scripts/v_ecommerce_', 'events/release-v-ecommerce', 'events/changed-ecommerce')):
        return 'B_REVIEW_ECOMMERCE_GATES'
    if path.startswith(('features/frontend-', 'verifiers/frontend-', 'scripts/frontend_', 'schemas/frontend-', 'templates/frontend/', 'docs/frontend-quality-loop.md')):
        return 'B_REVIEW_FRONTEND_GOVERNANCE'
    if path.startswith(('features/crossplanet-', 'verifiers/crossplanet-', 'scripts/crossplanet_', 'projects/v-ecommerce-crossplanet')):
        return 'B_REVIEW_CROSSPLANET'
    if path in {'README.md', 'projects/v-workspace.yaml', 'selfcheck/__main__.py', 'scripts/v_repair_task_control.py', 'scripts/state_ledger_health_harness.py', 'scripts/prototype_foundation_growth_gate.py', 'scripts/test_selfcheck_engineering.py', 'docs/project-adapter-framework.md', 'docs/plans/2026-05-21-critical-journey-release-gates.md'}:
        return 'B_REVIEW_SUPPORTING_CHANGES'
    return 'D_UNKNOWN_REVIEW_BEFORE_ACTION'


def collect(root: Path) -> dict[str, Any]:
    cp = run(['git', 'status', '--porcelain=v1'], cwd=root)
    if cp.returncode != 0:
        return {'ok': False, 'error': cp.stderr.strip() or cp.stdout.strip(), 'exit_code': cp.returncode}
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for line in cp.stdout.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:]
        if ' -> ' in path:
            path = path.split(' -> ', 1)[1]
        groups[classify(path)].append({'status': status, 'path': path})
    return {
        'ok': True,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'root': str(root),
        'total': sum(len(v) for v in groups.values()),
        'groups': {
            category: {
                **CATEGORY_META.get(category, CATEGORY_META['D_UNKNOWN_REVIEW_BEFORE_ACTION']),
                'count': len(items),
                'items': items,
            }
            for category, items in sorted(groups.items())
        },
    }


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        '# Control-plane Dirty Tree Inventory',
        '',
        f"Generated at: {data.get('generated_at')}",
        f"Total entries: {data.get('total')}",
        '',
        '## Summary',
    ]
    for category, payload in data.get('groups', {}).items():
        lines.append(f"- {category}: {payload.get('count')} — {payload.get('decision')}")
    lines.append('')
    lines.append('## Groups')
    for category, payload in data.get('groups', {}).items():
        lines.extend([
            '',
            f"### {category}",
            f"Decision: {payload.get('decision')}",
            f"Reason: {payload.get('reason')}",
            '',
        ])
        for item in payload.get('items', [])[:80]:
            lines.append(f"- `{item.get('status')}` `{item.get('path')}`")
        if len(payload.get('items', [])) > 80:
            lines.append(f"- ... {len(payload.get('items', [])) - 80} more")
    return '\n'.join(lines) + '\n'


def main() -> int:
    ap = argparse.ArgumentParser(description='Classify dirty files in the SelfCheck control-plane working tree.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json', 'markdown'], default='json')
    ap.add_argument('--no-write', action='store_true')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    data = collect(root)
    if data.get('ok') and not args.no_write:
        out_dir = root / 'reports' / 'v-control-plane-status'
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / 'dirty-inventory.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        (out_dir / 'dirty-inventory.md').write_text(render_markdown(data), encoding='utf-8')
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.format == 'json' else render_markdown(data), end='' if args.format == 'markdown' else '\n')
    return 0 if data.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())
