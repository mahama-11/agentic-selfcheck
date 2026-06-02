#!/usr/bin/env python3
from __future__ import annotations

import json
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'v_ecommerce_large_source_guard.py'


def run_case(root: Path, allowlist: Path | None = None, strict: bool = False) -> dict:
    argv = [sys.executable, str(SCRIPT), '--v-root', str(root), '--format', 'json']
    if allowlist:
        argv.extend(['--allowlist-json', str(allowlist)])
    if strict:
        argv.append('--strict')
    cp = subprocess.run(argv, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    try:
        payload = json.loads(cp.stdout)
    except Exception:
        payload = {'status': 'UNPARSEABLE', 'stdout': cp.stdout, 'stderr': cp.stderr}
    return {'returncode': cp.returncode, 'payload': payload, 'stderr': cp.stderr}


def write_lines(path: Path, count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(f'line {i}' for i in range(count)) + '\n', encoding='utf-8')


def main() -> int:
    py_compile.compile(str(SCRIPT), doraise=True)
    cases = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_lines(root / 'ecommerce-backend/internal/modules/newlarge/service.go', 801)
        result = run_case(root)
        cases.append({
            'case': 'new oversized source fails',
            'ok': result['returncode'] != 0 and result['payload'].get('findings') and result['payload']['findings'][0].get('failure_type') == 'ECOMMERCE_LARGE_SOURCE_FILE',
            **result,
        })
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rel = 'ecommerce-backend/internal/modules/visualworkflow/service.go'
        write_lines(root / rel, 5870)
        allow = root / 'allow.json'
        allow.write_text(json.dumps({rel: {'max_lines': 5870, 'task': 'legacy'}}), encoding='utf-8')
        result = run_case(root, allow)
        cases.append({
            'case': 'legacy baseline is pass with notes',
            'ok': bool(result['returncode'] == 0 and result['payload'].get('status') == 'PASS_WITH_NOTES' and result['payload'].get('legacy_remaining')),
            **result,
        })
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rel = 'ecommerce-backend/internal/modules/visualworkflow/service.go'
        write_lines(root / rel, 5871)
        allow = root / 'allow.json'
        allow.write_text(json.dumps({rel: {'max_lines': 5870, 'task': 'legacy'}}), encoding='utf-8')
        result = run_case(root, allow)
        cases.append({
            'case': 'legacy growth fails',
            'ok': result['returncode'] != 0 and result['payload'].get('findings') and result['payload']['findings'][0].get('failure_type') == 'ECOMMERCE_LEGACY_LARGE_SOURCE_GREW',
            **result,
        })
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rel = 'ecommerce-frontend/src/services/production.ts'
        write_lines(root / rel, 801)
        allow = root / 'allow.json'
        allow.write_text(json.dumps({rel: {'max_lines': 801, 'task': 'legacy'}}), encoding='utf-8')
        result = run_case(root, allow, strict=True)
        cases.append({
            'case': 'strict mode fails on every oversized file',
            'ok': bool(result['returncode'] != 0 and result['payload'].get('findings')),
            **result,
        })
    ok = all(case['ok'] for case in cases)
    print(json.dumps({'status': 'PASS' if ok else 'FAIL', 'cases': cases}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
