#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

SELFCHECK_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path('/root/work/v')
FEATURE = 'platform-stability-closed-loop-gates'


def main() -> int:
    verifier = sys.argv[1] if len(sys.argv) > 1 else 'platform-stability-closed-loop-alias'
    started = time.time()
    proc = subprocess.run(
        ['python3', 'scripts/platform_stability_closed_loop_smoke.py'],
        cwd=SELFCHECK_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    v_report = PROJECT_ROOT / 'reports' / FEATURE / f'{verifier}.json'
    local_report = SELFCHECK_ROOT / 'reports' / FEATURE / f'{verifier}.json'
    status = 'PASS' if proc.returncode == 0 else 'FAIL'
    payload = {
        'feature': FEATURE,
        'verifier': verifier,
        'status': status,
        'duration_seconds': round(time.time() - started, 3),
        'command': 'python3 scripts/platform_stability_closed_loop_smoke.py',
        'stdout_tail': proc.stdout[-4000:],
        'stderr_tail': proc.stderr[-4000:],
        'note': 'Alias verifier for non-static groups; the heavy same-run Platform/API/consumer commands are executed by platform-stability-closed-loop-static in the same loop.',
    }
    for report in (v_report, local_report):
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'status': status, 'report': str(local_report), 'v_report': str(v_report)}, ensure_ascii=False, indent=2))
    print(f'SELF_CHECK_EVIDENCE: {local_report}')
    return proc.returncode


if __name__ == '__main__':
    raise SystemExit(main())
