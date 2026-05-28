#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

FEATURE = 'ecommerce-frontend-style-governance'
DEFAULT_FRONTEND_ROOT = Path('/root/work/v/ecommerce-frontend')
DEFAULT_SELFCHECK_ROOT = Path('/root/work/agentic-selfcheck')


def run(cmd: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        cp = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return {
            'command': cmd,
            'cwd': str(cwd),
            'exit_code': cp.returncode,
            'stdout_tail': cp.stdout[-6000:],
            'stderr_tail': cp.stderr[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': cmd,
            'cwd': str(cwd),
            'exit_code': 124,
            'stdout_tail': (exc.stdout or '')[-6000:] if isinstance(exc.stdout, str) else '',
            'stderr_tail': 'timeout',
        }


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        return {'status': 'INVALID_JSON', 'error': str(exc), 'path': str(path)}


def top_drift_files(frontend_root: Path, limit: int = 8) -> list[dict[str, Any]]:
    baseline = load_json(frontend_root / 'scripts/ecommerce-style-consistency-baseline.json') or {}
    scan = baseline.get('scan') or {}
    rows = []
    for rel, counts in scan.items():
        total = sum(int(v or 0) for v in counts.values())
        if total > 0:
            rows.append({'path': rel, 'total': total, 'counts': counts})
    return sorted(rows, key=lambda r: (-r['total'], r['path']))[:limit]


def main() -> int:
    ap = argparse.ArgumentParser(description='SelfCheck static gate for Agent Ecommerce frontend style governance automation.')
    ap.add_argument('--frontend-root', default=str(DEFAULT_FRONTEND_ROOT))
    ap.add_argument('--selfcheck-root', default=str(DEFAULT_SELFCHECK_ROOT))
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--format', choices=['json', 'text'], default='json')
    args = ap.parse_args()

    frontend_root = Path(args.frontend_root).resolve()
    selfcheck_root = Path(args.selfcheck_root).resolve()
    report_dir = selfcheck_root / 'reports' / FEATURE
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / 'static.json'
    workspace_report_dir = Path('/root/work/v/reports') / FEATURE
    workspace_report_dir.mkdir(parents=True, exist_ok=True)
    workspace_report_path = workspace_report_dir / 'static.json'

    findings: list[dict[str, Any]] = []
    if not frontend_root.exists():
        findings.append({'severity': 'error', 'code': 'FRONTEND_ROOT_MISSING', 'path': str(frontend_root)})
    required = [
        'package.json',
        'scripts/ecommerce-frontend-automation-gate.mjs',
        'scripts/ecommerce-style-consistency.mjs',
        'scripts/ecommerce-style-consistency-baseline.json',
        'docs/frontend-style-governance.md',
        'docs/frontend-quality-governance.md',
        'docs/acceptance-tdd-governance.md',
        'docs/templates/frontend-cta-acceptance-matrix.md',
        'docs/agent-acceptance-tdd-workflow.md',
        'docs/design-system-registry.json',
        'src/index.css',
        'src/components/ui/Button.tsx',
        'src/components/ui/EcomShell.tsx',
        'scripts/ecommerce-eslint-baseline.json',
        'scripts/ecommerce-eslint-baseline-gate.mjs',
        'scripts/ecommerce-static-quality-baseline.json',
        'scripts/ecommerce-static-quality-gate.mjs',
        'scripts/ecommerce-design-system-registry-gate.mjs',
        'scripts/ecommerce-bundle-budget.mjs',
        'scripts/ecommerce-api-contract-gate.mjs',
        'scripts/ecommerce-lighthouse-budget.mjs',
        'contracts/ecommerce.openapi.json',
        'playwright.config.ts',
    ]
    for rel in required:
        if not (frontend_root / rel).exists():
            findings.append({'severity': 'error', 'code': 'REQUIRED_FILE_MISSING', 'path': rel})

    gate_result: dict[str, Any] | None = None
    style_report: dict[str, Any] | None = None
    evidence_manifest: dict[str, Any] | None = None
    repair_queue: dict[str, Any] | None = None
    eslint_baseline_report: dict[str, Any] | None = None
    static_quality_report: dict[str, Any] | None = None
    design_system_registry_report: dict[str, Any] | None = None
    api_contract_report: dict[str, Any] | None = None
    bundle_budget_report: dict[str, Any] | None = None
    lighthouse_budget_report: dict[str, Any] | None = None
    command_result: dict[str, Any] | None = None
    if not any(f['severity'] == 'error' for f in findings):
        command_result = run(['npm', 'run', 'frontend:gate', '--', '--report', 'reports/frontend-style-consistency/selfcheck-static.json'], frontend_root, args.timeout)
        gate_result = load_json(frontend_root / 'reports/frontend-style-consistency/selfcheck-static.json')
        style_report = load_json(frontend_root / 'reports/frontend-style-consistency/style-consistency-latest.json')
        evidence_manifest = load_json(frontend_root / 'reports/frontend-style-consistency/evidence-manifest.json')
        repair_queue = load_json(frontend_root / 'reports/frontend-style-consistency/style-drift-repair-queue.json')
        eslint_baseline_report = load_json(frontend_root / 'reports/frontend-quality/eslint-baseline-latest.json')
        static_quality_report = load_json(frontend_root / 'reports/frontend-quality/static-quality-latest.json')
        design_system_registry_report = load_json(frontend_root / 'reports/frontend-quality/design-system-registry-latest.json')
        api_contract_report = load_json(frontend_root / 'reports/frontend-quality/api-contract-latest.json')
        bundle_budget_report = load_json(frontend_root / 'reports/frontend-quality/bundle-budget-latest.json')
        lighthouse_budget_report = load_json(frontend_root / 'reports/frontend-quality/lighthouse-budget-latest.json')
        if command_result['exit_code'] != 0:
            findings.append({'severity': 'error', 'code': 'FRONTEND_GATE_FAILED', 'exit_code': command_result['exit_code']})
        if not gate_result or gate_result.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
            findings.append({'severity': 'error', 'code': 'FRONTEND_GATE_REPORT_NOT_PASS', 'status': gate_result.get('status') if isinstance(gate_result, dict) else None})
        if style_report and style_report.get('status') != 'PASS':
            findings.append({'severity': 'error', 'code': 'STYLE_CONSISTENCY_NOT_PASS', 'status': style_report.get('status')})
        if eslint_baseline_report and eslint_baseline_report.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
            findings.append({'severity': 'error', 'code': 'ESLINT_BASELINE_NOT_PASS', 'status': eslint_baseline_report.get('status')})
        if static_quality_report and static_quality_report.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
            findings.append({'severity': 'error', 'code': 'STATIC_QUALITY_NOT_PASS', 'status': static_quality_report.get('status')})
        if design_system_registry_report and design_system_registry_report.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
            findings.append({'severity': 'error', 'code': 'DESIGN_SYSTEM_REGISTRY_NOT_PASS', 'status': design_system_registry_report.get('status')})
        if api_contract_report and api_contract_report.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
            findings.append({'severity': 'error', 'code': 'API_CONTRACT_NOT_PASS', 'status': api_contract_report.get('status')})
        if bundle_budget_report and bundle_budget_report.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
            findings.append({'severity': 'error', 'code': 'BUNDLE_BUDGET_NOT_PASS', 'status': bundle_budget_report.get('status')})
        if lighthouse_budget_report and lighthouse_budget_report.get('status') not in {'PASS', 'PASS_WITH_NOTES'}:
            findings.append({'severity': 'error', 'code': 'LIGHTHOUSE_BUDGET_NOT_PASS', 'status': lighthouse_budget_report.get('status')})

    status = 'PASS' if not findings else ('FAIL' if any(f['severity'] == 'error' for f in findings) else 'PASS_WITH_NOTES')
    payload = {
        'feature': FEATURE,
        'status': status,
        'frontend_root': str(frontend_root),
        'selfcheck_report_path': str(report_path),
        'workspace_report_path': str(workspace_report_path),
        'policy': 'Style may evolve only through shared tokens/primitives with an accepted style-change proposal; page-level drift cannot increase.',
        'command_result': command_result,
        'frontend_gate_report': gate_result,
        'style_consistency_report': style_report,
        'visual_evidence_manifest': evidence_manifest,
        'style_drift_repair_queue': repair_queue,
        'eslint_baseline_report': eslint_baseline_report,
        'static_quality_report': static_quality_report,
        'design_system_registry_report': design_system_registry_report,
        'api_contract_report': api_contract_report,
        'bundle_budget_report': bundle_budget_report,
        'lighthouse_budget_report': lighthouse_budget_report,
        'burn_down_candidates': top_drift_files(frontend_root),
        'next_automation_hooks': [
            'business-gate selector maps ecommerce frontend style surfaces to this feature',
            'frontend:gate auto-generates Chromium screenshot evidence for Product Center / Production page UI changes when no accepted manifest exists',
            'frontend:gate fails global style file changes without accepted style-change proposal',
            'style drift repair queue is regenerated every gate run so historical drift has a machine-readable burn-down backlog',
            'ESLint and static accessibility/architecture baselines fail closed on any new debt while allowing old debt to burn down',
            'design-system registry keeps active/planned UI primitives and story-readiness requirements machine-readable',
            'API contracts are generated from contracts/ecommerce.openapi.json and checked by frontend:gate / ci:quick',
            'acceptance:TDD governance requires P0/P1 requirement semantics, acceptance matrix, RED/GREEN evidence, and runtime browser evidence before PASS',
            'Playwright smoke and screenshot-diff suites cover the critical Product Center / Production surfaces in ci:quick',
            'bundle and Lighthouse budgets block silent performance regressions',
        ],
        'findings': findings,
    }
    report_text = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
    report_path.write_text(report_text, encoding='utf-8')
    workspace_report_path.write_text(report_text, encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.format == 'json' else f"status={status}\nreport={report_path}\nworkspace_report={workspace_report_path}")
    return 0 if status != 'FAIL' else 1


if __name__ == '__main__':
    raise SystemExit(main())
