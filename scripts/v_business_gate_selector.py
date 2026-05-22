#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / 'config' / 'v-business-gate-selector.yaml'


def norm(path: str) -> str:
    return path.strip().replace('\\', '/').removeprefix('./')


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    if not isinstance(data, dict):
        raise ValueError(f'selector config must be a mapping: {path}')
    return data


def match_pattern(path: str, pattern: str) -> bool:
    path = norm(path)
    pattern = norm(pattern)
    if fnmatch.fnmatch(path, pattern):
        return True
    # Python fnmatch treats ** like *, but this explicit prefix path makes
    # directory-subtree intent obvious and stable for patterns ending in /**.
    if pattern.endswith('/**'):
        return path.startswith(pattern[:-3].rstrip('/') + '/')
    return False


def select_gates(files: list[str], config: dict[str, Any]) -> dict[str, Any]:
    feature_defs = config.get('features') or {}
    rules = config.get('rules') or []
    selected: dict[str, dict[str, Any]] = {}
    findings: list[dict[str, Any]] = []
    normalized = sorted({norm(f) for f in files if f and norm(f)})

    for file in normalized:
        matched = False
        for rule in rules:
            patterns = rule.get('patterns') or []
            if any(match_pattern(file, pattern) for pattern in patterns):
                matched = True
                for gate in rule.get('gates') or []:
                    spec = dict(feature_defs.get(gate) or {})
                    if not spec:
                        findings.append({'severity': 'error', 'file': file, 'rule': rule.get('id'), 'message': f'unknown gate: {gate}'})
                        continue
                    entry = selected.setdefault(gate, {
                        'feature': gate,
                        'event': spec.get('event'),
                        'groups': spec.get('groups'),
                        'command': spec.get('command'),
                        'blocking': bool(spec.get('blocking', True)),
                        'reason': spec.get('reason'),
                        'matched_rules': [],
                        'matched_files': [],
                    })
                    if rule.get('id') not in entry['matched_rules']:
                        entry['matched_rules'].append(rule.get('id'))
                    if file not in entry['matched_files']:
                        entry['matched_files'].append(file)
        if not matched:
            continue

    status = 'PASS' if not findings else 'FAIL'
    return {
        'status': status,
        'changed_files': normalized,
        'selected_gates': list(selected.values()),
        'findings': findings,
    }


def run_gate(root: Path, gate: dict[str, Any], timeout: int, dry_run: bool) -> dict[str, Any]:
    command = gate.get('command')
    if not command:
        return {'feature': gate.get('feature'), 'status': 'FAIL', 'exit_code': 127, 'stdout': '', 'stderr': 'missing gate command'}
    if dry_run:
        return {'feature': gate.get('feature'), 'status': 'DRY_RUN', 'exit_code': 0, 'command': command, 'stdout': '', 'stderr': ''}
    try:
        argv = shlex.split(command)
        if not argv:
            return {'feature': gate.get('feature'), 'status': 'FAIL', 'exit_code': 127, 'command': command, 'stdout': '', 'stderr': 'empty gate command'}
        proc = subprocess.run(argv, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return {
            'feature': gate.get('feature'),
            'status': 'PASS' if proc.returncode == 0 else 'FAIL',
            'exit_code': proc.returncode,
            'command': command,
            'stdout': proc.stdout[-4000:],
            'stderr': proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired:
        return {'feature': gate.get('feature'), 'status': 'FAIL', 'exit_code': 124, 'command': command, 'stdout': '', 'stderr': 'business gate timeout'}


def main() -> int:
    ap = argparse.ArgumentParser(description='Select required V business SelfCheck gates from changed files.')
    ap.add_argument('--root', default=str(ROOT))
    ap.add_argument('--config', default=str(DEFAULT_CONFIG))
    ap.add_argument('--changed-file', action='append', default=[])
    ap.add_argument('--run', action='store_true', help='Run selected business gates. Default only reports the selector decision.')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--format', choices=['json', 'text'], default='json')
    args = ap.parse_args()

    root = Path(args.root).resolve()
    config = load_config(Path(args.config).resolve())
    payload = select_gates(args.changed_file, config)
    payload['config'] = str(Path(args.config).resolve())
    payload['run_requested'] = bool(args.run)
    payload['dry_run'] = bool(args.dry_run)
    payload['executions'] = []

    if args.run and payload['selected_gates']:
        failures = 0
        for gate in payload['selected_gates']:
            result = run_gate(root, gate, args.timeout, args.dry_run)
            payload['executions'].append(result)
            if result.get('exit_code') != 0:
                failures += 1
        if failures:
            payload['status'] = 'FAIL'

    if args.format == 'json':
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print('status=' + payload['status'])
        for gate in payload['selected_gates']:
            print(f"gate={gate['feature']} files={len(gate['matched_files'])} rules={','.join(gate['matched_rules'])}")
        for finding in payload['findings']:
            print(f"finding={finding}")
    return 0 if payload['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
