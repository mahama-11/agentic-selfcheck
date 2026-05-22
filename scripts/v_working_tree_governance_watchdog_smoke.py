#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import py_compile
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description='Smoke test V working-tree governance watchdog fail-closed invariants.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json', 'text'], default='text')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    script = root / 'scripts' / 'v_working_tree_governance_watchdog.py'
    if not script.exists():
        print(f'missing script: {script}')
        return 2
    py_compile.compile(str(script), doraise=True)
    source = script.read_text(encoding='utf-8')
    checks = {
        'selector_exit_code_checked': "selector.get('exit_code') != 0" in source,
        'selector_status_fail_checked': "selector.get('status') == 'FAIL'" in source,
        'selector_findings_checked': "selector.get('findings')" in source,
        'selector_failure_type_reported': 'BUSINESS_GATE_SELECTOR_FAILED' in source,
        'failure_closed_loop_present': 'run_failure_closed_loop()' in source,
    }
    result = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'script': str(script)}
    if args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
