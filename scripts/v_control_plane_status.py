#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CRON_JOB_ROLES = {
    '0e0a0b9e6bb2': 'workflow evidence self-healing audit',
    '04925f44b90a': 'SelfCheck runtime service watchdog',
    'da227e480d8a': 'AI state ledger watchdog',
    'e72e4398fee8': 'SelfCheck repo daily governance sweep',
    '71ea35e98beb': 'V daily discovery / queue governance sweep',
    'be41037f9ef4': 'V 2h lightweight RepairTask executor',
    'e3c95c6dfa5d': 'V weekly closure-quality audit',
    '945640f35643': 'Ecommerce fixed Prep/Sandbox gate watchdog',
    '5956a3339eb8': 'V working-tree business gate watchdog',
    '4d0eca6a6eac': 'Idea inbox daily reminder',
}

CONTROL_PLANE_CRON_JOB_IDS = {
    job_id for job_id in CRON_JOB_ROLES if job_id != '4d0eca6a6eac'
}

SENSITIVE_MARKERS = (
    'api_key', 'apikey', 'secret', 'password', 'passwd', 'token', 'authorization',
    'bearer ', 'cookie', 'set-cookie', 'connection string', 'dsn=',
)


def run(argv: list[str], cwd: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def classify_path(path: str) -> str:
    if path.startswith('.hermes/workflows/'):
        return 'workflow_evidence'
    if path.startswith(('features/', 'verifiers/', 'events/', 'projects/', 'schemas/', 'journeys/')):
        return 'selfcheck_contracts'
    if path.startswith(('scripts/', 'selfcheck/', 'config/')):
        return 'control_plane_source'
    if path.startswith(('docs/', 'README', 'templates/')):
        return 'docs_templates'
    if path.startswith('reports/'):
        return 'generated_reports'
    return 'unknown'


def dirty_tree(root: Path) -> dict[str, Any]:
    cp = run(['git', 'status', '--porcelain=v1'], cwd=root, timeout=30)
    if cp.returncode != 0:
        return {'ok': False, 'error': cp.stderr.strip() or cp.stdout.strip()}
    lines = [line for line in cp.stdout.splitlines() if line.strip()]
    by_status: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for line in lines:
        status = line[:2]
        path = line[3:]
        if ' -> ' in path:
            path = path.split(' -> ', 1)[1]
        category = classify_path(path)
        by_status[status] += 1
        by_category[category] += 1
        if len(examples[category]) < 8:
            examples[category].append(path)
    return {
        'ok': True,
        'total': len(lines),
        'by_status': dict(by_status),
        'by_category': dict(by_category),
        'examples': dict(examples),
        'risk': 'dirty_control_plane' if lines else 'clean',
    }


def repair_task_status(selfcheck_root: Path, v_root: Path) -> dict[str, Any]:
    script = selfcheck_root / 'scripts' / 'v_repair_task_control.py'
    if not script.exists():
        return {'ok': False, 'error': f'missing {script}'}
    cp = run([sys.executable, str(script), 'status', '--selfcheck-root', str(selfcheck_root), '--v-root', str(v_root), '--format', 'json'], cwd=selfcheck_root, timeout=120)
    if cp.returncode != 0:
        return {'ok': False, 'error': cp.stderr.strip() or cp.stdout.strip(), 'exit_code': cp.returncode}
    try:
        data = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        return {'ok': False, 'error': f'invalid json: {exc}', 'stdout_tail': cp.stdout[-1000:]}
    data['ok'] = True
    return data


def parse_cron_list(text: str) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for raw in text.splitlines():
        line = raw.rstrip('\n')
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) >= 2 and len(parts[0]) == 12 and parts[1].startswith('['):
            if cur:
                jobs.append(cur)
            cur = {'job_id': parts[0], 'state': parts[1].strip('[]'), 'role': CRON_JOB_ROLES.get(parts[0], 'unclassified')}
            continue
        if cur is None:
            continue
        if stripped.startswith('Name:'):
            cur['name'] = stripped.split(':', 1)[1].strip()
        elif stripped.startswith('Schedule:'):
            cur['schedule'] = stripped.split(':', 1)[1].strip()
        elif stripped.startswith('Next run:'):
            cur['next_run'] = stripped.split(':', 1)[1].strip()
        elif stripped.startswith('Last run:'):
            cur['last_run'] = stripped.split(':', 1)[1].strip()
        elif 'Delivery failed:' in stripped:
            cur['delivery_error'] = stripped.split('Delivery failed:', 1)[1].strip()
        elif stripped.startswith('Script:'):
            cur['script'] = stripped.split(':', 1)[1].strip()
        elif stripped.startswith('Workdir:'):
            cur['workdir'] = stripped.split(':', 1)[1].strip()
    if cur:
        jobs.append(cur)
    return jobs


def latest_cron_output(job_id: str, output_root: Path) -> dict[str, Any]:
    job_dir = output_root / job_id
    files = sorted(job_dir.glob('*.md')) if job_dir.exists() else []
    if not files:
        return {'exists': False}
    latest = files[-1]
    # Read a bounded prefix only. Status projection must not become a second
    # durable store for arbitrary cron report content.
    text = latest.read_text(encoding='utf-8', errors='ignore')[:20000]
    response = text.split('## Response', 1)[-1] if '## Response' in text else text
    preview = ' '.join(response.strip().split())[:280]
    if any(marker in preview.lower() for marker in SENSITIVE_MARKERS):
        preview = '[REDACTED]'
    return {
        'exists': True,
        'path': str(latest),
        'silent': '[SILENT]' in response or 'Status:** silent' in text or 'silent (empty output)' in text,
        'size_bytes': latest.stat().st_size,
        'preview': preview,
    }


def cron_status(hermes_home: Path) -> dict[str, Any]:
    cp = run(['hermes', 'cron', 'list', '--all'], timeout=60)
    if cp.returncode != 0:
        return {'ok': False, 'error': cp.stderr.strip() or cp.stdout.strip()}
    # Keep this projection focused on engineering control-plane jobs. Personal
    # productivity cron output can contain unrelated user content and should not
    # be persisted in V/SelfCheck status reports.
    jobs = [job for job in parse_cron_list(cp.stdout) if job.get('job_id') in CONTROL_PLANE_CRON_JOB_IDS]
    output_root = hermes_home / 'cron' / 'output'
    for job in jobs:
        job['latest_output'] = latest_cron_output(job['job_id'], output_root)
    return {
        'ok': True,
        'count': len(jobs),
        'delivery_errors': [j for j in jobs if j.get('delivery_error')],
        'jobs': jobs,
    }


def overall_status(payload: dict[str, Any]) -> str:
    repair = payload.get('repair_tasks', {})
    cron = payload.get('cron', {})
    dirty = payload.get('dirty_tree', {})
    if not dirty.get('ok', False) or not repair.get('ok', False) or not cron.get('ok', False):
        return 'NEEDS_REPAIR'
    if repair.get('summary', {}).get('by_status', {}).get('verification_failed'):
        return 'NEEDS_REPAIR'
    if any(j.get('delivery_error') for j in cron.get('jobs', [])):
        return 'PASS_WITH_NOTES'
    if dirty.get('total', 0) > 0:
        return 'PASS_WITH_NOTES'
    return 'PASS'


def write_outputs(root: Path, payload: dict[str, Any]) -> None:
    out_dir = root / 'reports' / 'v-control-plane-status'
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'latest.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (out_dir / 'latest.md').write_text(render_markdown(payload), encoding='utf-8')


def render_markdown(payload: dict[str, Any]) -> str:
    repair_summary = payload.get('repair_tasks', {}).get('summary', {})
    dirty = payload.get('dirty_tree', {})
    cron = payload.get('cron', {})
    delivery_errors = cron.get('delivery_errors') or []
    lines = [
        '# V Control Plane Status',
        '',
        f"Status: {payload.get('status')}",
        f"Generated at: {payload.get('generated_at')}",
        '',
        '## Dirty tree',
        f"Total changed entries: {dirty.get('total', 'unknown')}",
        f"By category: `{json.dumps(dirty.get('by_category', {}), ensure_ascii=False)}`",
        '',
        '## RepairTask',
        f"Total: {repair_summary.get('total')}",
        f"Active: {repair_summary.get('active')}",
        f"Terminal: {repair_summary.get('terminal')}",
        f"By status: `{json.dumps(repair_summary.get('by_status', {}), ensure_ascii=False)}`",
        '',
        '## Cron',
        f"Jobs: {cron.get('count')}",
        f"Delivery errors: {len(delivery_errors)}",
    ]
    for job in delivery_errors[:5]:
        lines.append(f"- {job.get('job_id')} {job.get('name')}: {job.get('delivery_error')}")
    lines.extend(['', '## Evidence', f"JSON: `{payload.get('evidence', {}).get('json')}`"])
    return '\n'.join(lines) + '\n'


def main() -> int:
    ap = argparse.ArgumentParser(description='Summarize V/SelfCheck control-plane health.')
    ap.add_argument('--selfcheck-root', default='.')
    ap.add_argument('--v-root', default='/root/work/v')
    ap.add_argument('--hermes-home', default='/root/.hermes')
    ap.add_argument('--format', choices=['json', 'markdown'], default='json')
    ap.add_argument('--no-write', action='store_true')
    args = ap.parse_args()

    selfcheck_root = Path(args.selfcheck_root).resolve()
    v_root = Path(args.v_root).resolve()
    hermes_home = Path(args.hermes_home).resolve()
    payload: dict[str, Any] = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'selfcheck_root': str(selfcheck_root),
        'v_root': str(v_root),
        'dirty_tree': dirty_tree(selfcheck_root),
        'repair_tasks': repair_task_status(selfcheck_root, v_root),
        'cron': cron_status(hermes_home),
    }
    payload['status'] = overall_status(payload)
    payload['evidence'] = {
        'json': str(selfcheck_root / 'reports' / 'v-control-plane-status' / 'latest.json'),
        'markdown': str(selfcheck_root / 'reports' / 'v-control-plane-status' / 'latest.md'),
    }
    if not args.no_write:
        write_outputs(selfcheck_root, payload)
    if args.format == 'json':
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
