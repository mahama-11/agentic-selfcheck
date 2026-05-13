#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

CASES = [
    ('good-c', 'C', True),
    ('good-d', 'D', True),
    ('bad-missing-references', 'C', False),
    ('bad-antipattern', 'C', False),
    ('bad-low-score', 'D', False),
    ('bad-visual-source', 'C', False),
    ('bad-malformed-payload', 'C', False),
    ('bad-string-score', 'C', False),
    ('bad-extra-nested-field', 'C', False),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    results = []
    ok = True
    for name, risk, should_pass in CASES:
        wf = f'.hermes/workflows/frontend-reference-aware-critic-smoke/{name}'
        cmd = ['scripts/frontend_reference_aware_critic.py', '--root', '.', '--workflow', wf, '--risk', risk, '--input-json', f'{wf}/reference-aware-input.json', '--format', 'json']
        cp = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        passed = cp.returncode == 0
        if passed != should_pass:
            ok = False
        results.append({'case': name, 'expected': 'PASS' if should_pass else 'FAIL', 'actual': 'PASS' if passed else 'FAIL', 'returncode': cp.returncode, 'stdout': cp.stdout[-1600:], 'stderr': cp.stderr[-1600:]})
    result = {'status': 'PASS' if ok else 'FAIL', 'cases': results}
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == 'json' else 'status=' + result['status'])
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
