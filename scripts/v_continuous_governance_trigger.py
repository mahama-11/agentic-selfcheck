#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

SELF_ROOT = Path('/root/work/agentic-selfcheck')
V_ROOT = Path('/root/work/v')
DOC_SUFFIXES = {'.md', '.mdx', '.rst'}
CODE_SUFFIXES = {'.py', '.go', '.ts', '.tsx', '.js', '.jsx', '.json', '.yaml', '.yml', '.toml', '.mod', '.sum'}
FRONTEND_SUFFIXES = {'.ts', '.tsx', '.js', '.jsx', '.vue', '.svelte', '.html', '.css', '.scss'}
FRONTEND_PATH_PARTS = {'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend', 'src/pages', 'src/components', 'src/views', 'app/routes', 'routes', 'templates'}


def norm(p: str) -> str:
    return p.strip().replace('\\', '/').lstrip('./')


def events_for_path(p: str) -> set[str]:
    p = norm(p)
    suffix = Path(p).suffix.lower()
    name = Path(p).name
    events: set[str] = set()
    if p.startswith(('docs/', 'README', '.hermes/workflows/')) or suffix in DOC_SUFFIXES:
        events.add('v.governance.changed.docs')
    if suffix in CODE_SUFFIXES or p.split('/')[0] in {
        'platform-backend', 'ecommerce-backend', 'menu-backend', 'kyc-backend',
        'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend', 'tools'
    } or name in {'package.json', 'go.mod', 'pyproject.toml', 'Makefile'}:
        events.add('v.governance.changed.code')
    if (suffix in FRONTEND_SUFFIXES and any(part in p for part in FRONTEND_PATH_PARTS)) or p.split('/')[0] in {
        'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend'
    }:
        events.add('v.governance.changed.frontend')
    return events


def git_files(repo: Path, mode: str) -> list[str]:
    commands = {
        'staged': ['git', 'diff', '--name-only', '--cached'],
        'working': ['git', 'diff', '--name-only'],
        'head': ['git', 'diff', '--name-only', 'HEAD'],
        'pre-push': ['git', 'diff', '--name-only', '@{u}...HEAD'],
    }
    try:
        proc = subprocess.run(commands[mode], cwd=repo, text=True, capture_output=True, timeout=30)
        if proc.returncode != 0 and mode == 'pre-push':
            proc = subprocess.run(['git', 'diff', '--name-only', 'HEAD~1...HEAD'], cwd=repo, text=True, capture_output=True, timeout=30)
        if proc.returncode != 0:
            return []
        try:
            prefix = str(repo.resolve().relative_to(V_ROOT.resolve()))
        except Exception:
            prefix = repo.name
        return [norm(str(Path(prefix) / line.strip())) for line in proc.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def trigger(event: str, files: list[str], source: str, dry_run: bool, timeout: int) -> dict:
    payload = {
        'source': source,
        'changed_files': files,
        'target_root': str(V_ROOT),
        'triggered_by': 'v_continuous_governance_trigger.py',
    }
    argv = [
        sys.executable, '-m', 'selfcheck', 'trigger', '--root', str(SELF_ROOT),
        '--event', event, '--source', source, '--payload', json.dumps(payload, ensure_ascii=False),
        '--timeout', str(timeout),
    ]
    if dry_run:
        argv.append('--dry-run')
    proc = subprocess.run(argv, cwd=SELF_ROOT, text=True, capture_output=True, timeout=timeout + 30)
    return {'event': event, 'exit_code': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-4000:]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo-root', default='.')
    ap.add_argument('--changed-file', action='append', default=[])
    ap.add_argument('--git-mode', choices=['staged', 'working', 'head', 'pre-push'])
    ap.add_argument('--source', default='local')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--timeout', type=int, default=300)
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    files = list(args.changed_file)
    if args.git_mode:
        files += git_files(repo, args.git_mode)
    files = sorted({norm(f) for f in files if f.strip()})
    events = sorted({event for file in files for event in events_for_path(file)})
    report = {
        'status': 'NOOP' if not events else 'PASS',
        'source': args.source,
        'repo_root': str(repo),
        'dry_run': args.dry_run,
        'changed_files': files,
        'events': [],
    }
    failures = 0
    for event in events:
        result = trigger(event, files, args.source, args.dry_run, args.timeout)
        report['events'].append(result)
        if result['exit_code'] != 0:
            failures += 1
    if failures:
        report['status'] = 'FAIL'
    out = SELF_ROOT / 'reports' / 'v-continuous-governance-trigger'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
