#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DOC_EVENTS = {"governance.changed.docs", "governance.changed.hermes"}
CODE_EVENTS = {"governance.changed.code"}
SKILL_EVENTS = {"governance.changed.skills"}
PITFALL_EVENTS = {"governance.changed.pitfalls", "governance.changed.hermes"}
HERMES_EVENTS = {"governance.changed.hermes"}
SOURCE_SUFFIXES = {'.py','.go','.ts','.tsx','.js','.jsx','.json','.yaml','.yml','.toml','.mod','.sum'}
DOC_SUFFIXES = {'.md','.mdx','.rst'}


def norm(path: str) -> str:
    return path.strip().replace('\\','/').lstrip('./')


def event_set_for_path(path: str) -> set[str]:
    p = norm(path)
    events: set[str] = set()
    name = Path(p).name
    suffix = Path(p).suffix.lower()
    if p.startswith(('docs/','README','.hermes/workflows/')) or suffix in DOC_SUFFIXES:
        events |= DOC_EVENTS
    if p.startswith(('features/','verifiers/','schemas/','capabilities/','projects/','events/','loops/','repair-policies/','reports/','.hermes/workflows/')):
        events |= HERMES_EVENTS
    if p.startswith('pitfalls/') or p == 'schemas/pitfall.schema.json':
        events |= PITFALL_EVENTS
    if p.startswith(('.hermes/skills/','skills/')) or '/skills/' in p or p.endswith('/SKILL.md'):
        events |= SKILL_EVENTS
    if p.startswith(('scripts/','selfcheck/')) or suffix in SOURCE_SUFFIXES or name in {'package.json','go.mod','pyproject.toml','Makefile'}:
        events |= CODE_EVENTS
    return events


def git_changed_files(root: Path, mode: str) -> list[str]:
    commands = {
        'staged': ['git','diff','--name-only','--cached'],
        'working': ['git','diff','--name-only'],
        'head': ['git','diff','--name-only','HEAD'],
        'pre-push': ['git','diff','--name-only','@{u}...HEAD'],
    }
    try:
        proc = subprocess.run(commands[mode], cwd=root, text=True, capture_output=True, timeout=30)
        if proc.returncode != 0 and mode == 'pre-push':
            proc = subprocess.run(['git','diff','--name-only','HEAD~1...HEAD'], cwd=root, text=True, capture_output=True, timeout=30)
        if proc.returncode != 0:
            return []
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def run_trigger(root: Path, event: str, source: str, files: list[str], dry_run: bool, timeout: int) -> dict:
    payload = {'source': source, 'changed_files': files, 'triggered_by': 'continuous_governance_trigger.py'}
    argv = [sys.executable, '-m', 'selfcheck', 'trigger', '--root', str(root), '--event', event, '--source', source, '--payload', json.dumps(payload, ensure_ascii=False), '--timeout', str(timeout)]
    if dry_run:
        argv.append('--dry-run')
    proc = subprocess.run(argv, cwd=root, text=True, capture_output=True, timeout=timeout + 30)
    return {'event': event, 'exit_code': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-4000:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--changed-file', action='append', default=[])
    ap.add_argument('--changed-files-file')
    ap.add_argument('--git-mode', choices=['staged','working','head','pre-push'])
    ap.add_argument('--source', default='local')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--timeout', type=int, default=300)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    files = list(args.changed_file)
    if args.changed_files_file:
        files += [line.strip() for line in Path(args.changed_files_file).read_text(encoding='utf-8').splitlines() if line.strip()]
    if args.git_mode:
        files += git_changed_files(root, args.git_mode)
    files = sorted({norm(f) for f in files if f.strip()})
    events = sorted({ev for f in files for ev in event_set_for_path(f)})
    report = {'status': 'NOOP' if not events else 'PASS', 'source': args.source, 'dry_run': args.dry_run, 'changed_files': files, 'events': [], 'event_count': len(events)}
    failures = 0
    for ev in events:
        result = run_trigger(root, ev, args.source, files, args.dry_run, args.timeout)
        report['events'].append(result)
        if result['exit_code'] != 0:
            failures += 1
    if failures:
        report['status'] = 'FAIL'
    outdir = root / 'reports' / 'continuous-governance-trigger'
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / 'latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
