#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

ARCHIVE = Path('/root/.hermes/archive/agentic-selfcheck-crossplanet-draft-20260522-200831')
BACKEND = Path('/root/work/v-worktrees/crossplanet-listing-strategy-backend')
FRONTEND = Path('/root/work/v-worktrees/crossplanet-listing-strategy-frontend')
FORBIDDEN_REGISTERED = [
    Path('features/crossplanet-listing-strategy-input.yaml'),
    Path('features/crossplanet-template-skill-ia.yaml'),
    Path('scripts/crossplanet_listing_strategy_gate.py'),
    Path('scripts/crossplanet_template_skill_ia_gate.py'),
]


def git_status(repo: Path) -> list[str]:
    cp = subprocess.run(['git', '-C', str(repo), 'status', '--short'], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    if cp.returncode != 0:
        raise RuntimeError(cp.stdout.strip())
    return [line.strip() for line in cp.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description='CrossPlanet/List Strategy gate repair quarantine checker.')
    parser.add_argument('--selfcheck-root', default='.')
    parser.add_argument('--format', choices=['json', 'text'], default='json')
    args = parser.parse_args()
    root = Path(args.selfcheck_root).resolve()
    findings: list[dict[str, Any]] = []
    if not ARCHIVE.exists():
        findings.append({'severity': 'error', 'code': 'ARCHIVED_DRAFT_MISSING', 'path': str(ARCHIVE)})
    for rel in FORBIDDEN_REGISTERED:
        if (root / rel).exists():
            findings.append({'severity': 'blocker', 'code': 'IMMATURE_CROSSPLANET_DRAFT_REGISTERED', 'path': str(rel)})
    if not BACKEND.exists():
        findings.append({'severity': 'error', 'code': 'BACKEND_WORKTREE_MISSING', 'path': str(BACKEND)})
    if not FRONTEND.exists():
        findings.append({'severity': 'error', 'code': 'FRONTEND_WORKTREE_MISSING', 'path': str(FRONTEND)})
    backend_dirty = len(git_status(BACKEND)) if BACKEND.exists() else None
    frontend_dirty = len(git_status(FRONTEND)) if FRONTEND.exists() else None
    payload: dict[str, Any] = {
        'status': 'FAIL' if any(f['severity'] in {'error', 'blocker'} for f in findings) else 'PASS_WITH_NOTES',
        'merge_state': 'QUARANTINED_UNTIL_REPAIRED_GATES_PASS',
        'archive': str(ARCHIVE),
        'backend_dirty_count': backend_dirty,
        'frontend_dirty_count': frontend_dirty,
        'required_repairs': [
            'replace hardcoded roots with explicit project/worktree roots',
            'remove stale report dependencies; produce same-run evidence',
            'replace brittle internal-copy browser checks with durable user-facing behavior assertions',
            'classify generated workflow evidence separately from required governance evidence',
            'run backend and frontend checks from intended roots in the same SelfCheck loop',
        ],
        'findings': findings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.format == 'json' else payload)
    return 0 if payload['status'] != 'FAIL' else 1


if __name__ == '__main__':
    raise SystemExit(main())
