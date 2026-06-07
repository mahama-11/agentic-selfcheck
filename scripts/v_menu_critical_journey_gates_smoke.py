#!/usr/bin/env python3
from __future__ import annotations
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V_ROOT = ROOT.parent / 'v'
REPORT_DIR = V_ROOT / 'reports' / 'evidence-contract' / 'menu-studio-core-chain'


def emit(status: str, findings: list[dict]) -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        'feature': 'menu-critical-journey-gates',
        'verifier': 'menu-critical-journey-gates-smoke',
        'status': status,
        'findings': findings,
        'generated_at_epoch': time.time(),
    }
    (REPORT_DIR / 'menu-critical-journey-gates-smoke.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == 'PASS' else 1


def main() -> int:
    findings: list[dict] = []
    selector = subprocess.run([
        sys.executable,
        'scripts/v_business_gate_selector.py',
        '--changed-file', 'menu-backend/internal/modules/studio/service_types.go',
        '--changed-file', 'menu-backend/internal/modules/templatecenter/service.go',
        '--changed-file', 'menu-frontend/src/pages/dashboard/DashboardTemplateCenterPage.tsx',
        '--changed-file', 'menu-frontend/tests/e2e/menu.business-flow.spec.ts',
        '--format', 'json',
    ], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if selector.returncode != 0:
        findings.append({'severity': 'error', 'message': 'Menu critical journey selector failed', 'stderr': selector.stderr[-1000:]})
    else:
        payload = json.loads(selector.stdout)
        gates = {g.get('feature') for g in payload.get('selected_gates', [])}
        if 'menu-critical-journey-gates' not in gates:
            findings.append({'severity': 'error', 'message': 'selector did not select menu-critical-journey-gates', 'selected_gates': sorted(gates)})
        bridge = next((g for g in payload.get('selected_gates', []) if g.get('feature') == 'menu-critical-journey-gates'), {})
        if 'SELFCHECK_ALLOW_PARTIAL=1' not in bridge.get('command', ''):
            findings.append({'severity': 'error', 'message': 'menu-critical-journey-gates must allow bounded partial evidence for approval-gated live smoke', 'command': bridge.get('command', '')})
    bridge_smoke = subprocess.run([sys.executable, 'scripts/v_menu_contract_evidence_bridge_smoke.py'], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if bridge_smoke.returncode != 0:
        findings.append({'severity': 'error', 'message': 'underlying Menu evidence bridge smoke failed', 'stdout': bridge_smoke.stdout[-1000:], 'stderr': bridge_smoke.stderr[-1000:]})
    return emit('PASS' if not findings else 'FAIL', findings)


if __name__ == '__main__':
    raise SystemExit(main())
