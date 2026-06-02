#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def run(argv: list[str], cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser(description='Smoke test P0/P1 failure closed loop controller.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json', 'text'], default='text')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    script = root / 'scripts' / 'v_failure_closed_loop.py'
    if not script.exists():
        print(f'missing script: {script}', file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix='v-failure-closed-loop-smoke-') as td:
        tmp = Path(td)
        # Minimal isolated SelfCheck-like root: copy only the controller script so the
        # smoke can mutate reports/.hermes without polluting the real ledger.
        (tmp / 'scripts').mkdir(parents=True)
        shutil.copy2(script, tmp / 'scripts' / 'v_failure_closed_loop.py')
        report = {
            'feature': 'synthetic-ecommerce-gate',
            'status': 'NEEDS_REPAIR',
            'attempt': 1,
            'groups': ['api'],
            'failures': [{
                'group': 'api',
                'verifier': 'synthetic-api-smoke',
                'status': 'FAIL',
                'exit_code': 1,
                'report_path': str(tmp / 'reports' / 'api_key=SECRET123' / 'synthetic-api-smoke.json'),
                'reason': 'schema contract mismatch: unexpected field ready',
            }],
        }
        report_path = tmp / 'reports' / 'loops' / 'synthetic-ecommerce-gate' / 'latest.json'
        write_json(report_path, report)

        outputs = []
        for i in range(3):
            cp = run([sys.executable, 'scripts/v_failure_closed_loop.py', 'ingest', '--root', str(tmp), '--report', str(report_path), '--source', f'smoke-{i}-api_key=SECRET123', '--format', 'json'], tmp)
            outputs.append({'iteration': i + 1, 'exit_code': cp.returncode, 'stdout': cp.stdout, 'stderr': cp.stderr})
            if cp.returncode != 0:
                print(json.dumps({'status': 'FAIL', 'step': 'ingest', 'outputs': outputs}, ensure_ascii=False, indent=2))
                return 1

        ledger_path = tmp / 'reports' / 'v-failure-closed-loop' / 'ledger.json'
        latest_path = tmp / 'reports' / 'v-failure-closed-loop' / 'latest.json'
        ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
        latest = json.loads(latest_path.read_text(encoding='utf-8'))
        incidents = ledger.get('incidents') or []
        spec = importlib.util.spec_from_file_location('v_failure_closed_loop_under_test', tmp / 'scripts' / 'v_failure_closed_loop.py')
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        redacted_sample = module.redact_sensitive_text('token=SECRET123 Authorization: Bearer abcdefghijklmnop')
        persisted_text = '\n'.join(p.read_text(encoding='utf-8') for p in [ledger_path, latest_path, *list((tmp / '.hermes' / 'dispatch' / 'v-failure-closed-loop').glob('*.md')), *list((tmp / 'reports' / 'v-failure-closed-loop' / 'architecture-escalations').glob('*.md'))])
        checks = {
            'ledger_exists': ledger_path.exists(),
            'latest_exists': latest_path.exists(),
            'one_incident': len(incidents) == 1,
            'dispatch_created_before_escalation': any((tmp / '.hermes' / 'dispatch' / 'v-failure-closed-loop').glob('*.md')),
            'escalated_after_three_observations': incidents and incidents[0].get('status') == 'ESCALATE_ARCHITECTURE' and incidents[0].get('observations') == 3,
            'escalation_card_created': bool(list((tmp / 'reports' / 'v-failure-closed-loop' / 'architecture-escalations').glob('*.md'))),
            'bucket_classified': incidents and incidents[0].get('bucket') == 'api_contract_drift',
            'latest_points_to_ledger': latest.get('ledger') == str(ledger_path),
            'secret_redacted': 'SECRET123' not in redacted_sample and 'abcdefghijklmnop' not in redacted_sample and redacted_sample.count('[REDACTED]') >= 2,
            'persisted_evidence_redacted': 'SECRET123' not in persisted_text and 'api_key=[REDACTED]' in persisted_text,
        }
        ok = all(checks.values())
        result = {'status': 'PASS' if ok else 'FAIL', 'checks': checks, 'ledger_summary': ledger.get('summary'), 'latest': latest}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == 'json' else result['status'])
        return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
