#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SELF_ROOT = Path('/root/work/agentic-selfcheck')
V_ROOT = Path('/root/work/v')
STATE_PATH = SELF_ROOT / 'reports' / 'v-working-tree-governance-watchdog' / 'state.json'
LATEST_PATH = SELF_ROOT / 'reports' / 'v-working-tree-governance-watchdog' / 'latest.json'
CANONICAL_REPOS = [
    'platform-backend', 'ecommerce-backend', 'menu-backend', 'kyc-backend',
    'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend',
]


def run(cmd: list[str], cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def discover_repos() -> list[Path]:
    repos: list[Path] = []
    seen: set[Path] = set()
    for name in CANONICAL_REPOS:
        repo = V_ROOT / name
        if (repo / '.git').exists() and repo not in seen:
            repos.append(repo)
            seen.add(repo)
    for git_path in V_ROOT.glob('*/.git'):
        repo = git_path.parent
        if repo not in seen:
            repos.append(repo)
            seen.add(repo)
    return repos


def canonical_prefix(repo: Path) -> str:
    name = repo.name
    for canonical in sorted(CANONICAL_REPOS, key=len, reverse=True):
        if name == canonical or name.startswith(canonical + '-'):
            return canonical
    return name


def porcelain_changed_files(repo: Path) -> list[str]:
    cp = run(['git', 'status', '--porcelain=v1', '-z'], repo, timeout=30)
    if cp.returncode != 0:
        return []
    files: list[str] = []
    entries = cp.stdout.split('\0')
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        if status.startswith('R') or status.startswith('C'):
            # porcelain -z emits old path in this entry and new path in next entry.
            if i < len(entries) and entries[i]:
                path = entries[i]
                i += 1
        if path:
            files.append(path.replace('\\', '/'))
    return sorted(set(files))


def file_digest(repo: Path, rel: str) -> str:
    path = repo / rel
    if not path.exists() or path.is_dir():
        return 'missing-or-dir'
    h = hashlib.sha256()
    try:
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:
        return f'error:{type(exc).__name__}'


def repo_signature(repo: Path, files: list[str]) -> str:
    h = hashlib.sha256()
    h.update('\n'.join(files).encode())
    # Include tracked diff bytes so repeated edits to the same files retrigger.
    cp = run(['git', 'diff', '--no-ext-diff', '--binary', 'HEAD', '--', *files], repo, timeout=120) if files else None
    if cp and cp.stdout:
        h.update(cp.stdout.encode(errors='ignore'))
    for rel in files:
        # Untracked files are not in git diff HEAD; hash all file contents as a cheap universal guard.
        h.update(rel.encode())
        h.update(file_digest(repo, rel).encode())
    return h.hexdigest()


def prefixed_files(repo: Path, files: list[str]) -> list[str]:
    prefix = canonical_prefix(repo)
    return [f'{prefix}/{f}' for f in files]


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {'repos': {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {'repos': {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def select_business_gates(files: list[str]) -> dict[str, Any]:
    argv = [sys.executable, 'scripts/v_business_gate_selector.py', '--root', str(SELF_ROOT), '--format', 'json']
    for file in files:
        argv.extend(['--changed-file', file])
    cp = run(argv, SELF_ROOT, timeout=60)
    try:
        payload = json.loads(cp.stdout) if cp.stdout.strip() else {}
    except Exception:
        payload = {}
    payload['exit_code'] = cp.returncode
    payload['stderr'] = cp.stderr[-2000:]
    return payload


def run_trigger(repo: Path, files: list[str], timeout: int) -> dict[str, Any]:
    argv = [
        sys.executable, 'scripts/v_continuous_governance_trigger.py',
        '--repo-root', str(repo),
        '--source', 'cron',
        '--timeout', str(timeout),
        '--run-business-gates',
        '--no-enforce-frontend-implementation',
    ]
    for file in files:
        argv.extend(['--changed-file', file])
    cp = run(argv, SELF_ROOT, timeout=timeout + 90)
    try:
        parsed = json.loads(cp.stdout) if cp.stdout.strip() else {}
        payload: dict[str, Any] = parsed if isinstance(parsed, dict) else {'raw_stdout': cp.stdout[-4000:]}
    except Exception:
        payload: dict[str, Any] = {'raw_stdout': cp.stdout[-4000:]}
    payload['exit_code'] = cp.returncode
    payload['stderr'] = cp.stderr[-4000:]
    return payload


def run_failure_closed_loop() -> dict[str, Any]:
    argv = [
        sys.executable, 'scripts/v_failure_closed_loop.py', 'ingest',
        '--root', str(SELF_ROOT),
        '--report', str(LATEST_PATH),
        '--source', 'working-tree-watchdog',
        '--format', 'json',
    ]
    cp = run(argv, SELF_ROOT, timeout=60)
    try:
        payload = json.loads(cp.stdout) if cp.stdout.strip() else {}
    except Exception:
        payload: dict[str, Any] = {'raw_stdout': cp.stdout[-4000:]}
    payload['exit_code'] = cp.returncode
    payload['stderr'] = cp.stderr[-3000:]
    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description='Run continuous V working-tree governance before commit/push.')
    ap.add_argument('--quiet-seconds', type=int, default=900, help='Require dirty signature to be stable this long before running heavy gates.')
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--format', choices=['json', 'text'], default='text')
    args = ap.parse_args()

    now = time.time()
    state = load_state()
    state.setdefault('repos', {})
    report: dict[str, Any] = {
        'status': 'SILENT',
        'source': 'v_working_tree_governance_watchdog.py',
        'quiet_seconds': args.quiet_seconds,
        'checked_at_epoch': now,
        'repos': [],
        'executed': [],
        'failures': [],
    }

    for repo in discover_repos():
        rel_files = porcelain_changed_files(repo)
        key = str(repo)
        entry = state['repos'].setdefault(key, {})
        if not rel_files:
            entry.clear()
            report['repos'].append({'repo': key, 'status': 'CLEAN'})
            continue
        full_files = prefixed_files(repo, rel_files)
        selector = select_business_gates(full_files)
        selected = selector.get('selected_gates') or []
        sig = repo_signature(repo, rel_files)
        if entry.get('signature') != sig:
            entry.update({'signature': sig, 'first_seen_at': now, 'last_change_at': now, 'last_seen_files': full_files, 'last_status': 'PENDING_QUIET'})
        age = now - float(entry.get('last_change_at') or now)
        repo_report = {
            'repo': key,
            'status': 'DIRTY',
            'changed_count': len(full_files),
            'selected_gates': [g.get('feature') for g in selected if isinstance(g, dict)],
            'signature_age_seconds': round(age, 1),
        }
        selector_failed = selector.get('exit_code') != 0 or selector.get('status') == 'FAIL' or bool(selector.get('findings'))
        if selector_failed:
            entry['last_status'] = 'FAIL'
            failure = {**repo_report, 'status': 'FAIL', 'failure_type': 'BUSINESS_GATE_SELECTOR_FAILED', 'selector': selector}
            report['repos'].append(failure)
            report['failures'].append(failure)
            continue
        if not selected:
            entry['last_status'] = 'NO_BUSINESS_GATES'
            report['repos'].append({**repo_report, 'status': 'NO_BUSINESS_GATES', 'selector': selector})
            continue
        already_passed = entry.get('last_run_signature') == sig and entry.get('last_status') == 'PASS'
        if already_passed and not args.force:
            report['repos'].append({**repo_report, 'status': 'ALREADY_PASSED'})
            continue
        if age < args.quiet_seconds and not args.force:
            report['repos'].append({**repo_report, 'status': 'WAITING_FOR_QUIET_WINDOW'})
            continue
        trigger = run_trigger(repo, full_files, args.timeout)
        ok = trigger.get('exit_code') == 0 and trigger.get('status') == 'PASS'
        entry['last_run_at'] = now
        entry['last_run_signature'] = sig
        entry['last_status'] = 'PASS' if ok else 'FAIL'
        entry['last_report'] = trigger
        executed = {**repo_report, 'status': 'PASS' if ok else 'FAIL', 'trigger': trigger}
        report['executed'].append(executed)
        report['repos'].append(executed)
        if not ok:
            report['failures'].append(executed)

    if report['failures']:
        report['status'] = 'FAIL'
    elif report['executed']:
        # For no_agent cron this is intentionally silent on PASS to avoid notification noise.
        report['status'] = 'PASS_SILENT'
    save_state(state)
    LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if report['failures']:
        report['failure_closed_loop'] = run_failure_closed_loop()
        LATEST_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    if args.format == 'json':
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if report['status'] == 'FAIL':
            print('V working-tree governance FAIL')
            for failure in report['failures']:
                gates = ','.join(failure.get('selected_gates') or [])
                print(f"repo={failure['repo']} gates={gates} changed={failure['changed_count']}")
                trigger = failure.get('trigger') or {}
                print((trigger.get('stderr') or trigger.get('raw_stdout') or json.dumps(trigger, ensure_ascii=False))[-3000:])
            closed_loop = report.get('failure_closed_loop') or {}
            if closed_loop:
                print(f"failure_closed_loop={closed_loop.get('ledger')} status={closed_loop.get('status')}")
            print(f'report={LATEST_PATH}')
        # PASS/SILENT prints nothing so cron no_agent stays quiet.
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
