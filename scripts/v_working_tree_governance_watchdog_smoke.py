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
        'large_changed_file_failure_reported': 'LARGE_CHANGED_SOURCE_FILE' in source,
        'large_changed_file_lines_threshold': 'MAX_CHANGED_SOURCE_LINES = 800' in source,
        'large_changed_file_bytes_threshold': 'MAX_CHANGED_SOURCE_BYTES = 1024 * 1024' in source,
        'v_worktrees_discovered': "V_WORKTREES_ROOT.glob('*/*/.git')" in source,
        'failure_closed_loop_present': 'run_failure_closed_loop()' in source,
        'git_status_timeout_fail_closed': 'GIT_STATUS_TIMEOUT' in source and 'status_failure' in source,
        'subprocess_timeout_caught': 'except subprocess.TimeoutExpired' in source,
    }
    result = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'script': str(script)}
    if args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result)
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
