#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(argv: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def main() -> int:
    ap = argparse.ArgumentParser(description='Smoke test V control-plane status projection.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--v-root', default='/root/work/v')
    ap.add_argument('--format', choices=['json', 'text'], default='text')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    script = root / 'scripts' / 'v_control_plane_status.py'
    if not script.exists():
        print(f'missing script: {script}', file=sys.stderr)
        return 2
    cp = run([sys.executable, str(script), '--selfcheck-root', str(root), '--v-root', args.v_root, '--format', 'json'], cwd=root)
    if cp.returncode != 0:
        print(json.dumps({'status': 'FAIL', 'step': 'run_status', 'exit_code': cp.returncode, 'stdout': cp.stdout[-1000:], 'stderr': cp.stderr[-1000:]}, ensure_ascii=False, indent=2))
        return 1
    inventory_script = root / 'scripts' / 'v_control_plane_dirty_inventory.py'
    inventory_cp = run([sys.executable, str(inventory_script), '--root', str(root), '--format', 'json'], cwd=root) if inventory_script.exists() else subprocess.CompletedProcess([], 2, '', f'missing {inventory_script}')
    if inventory_cp.returncode != 0:
        print(json.dumps({'status': 'FAIL', 'step': 'run_inventory', 'exit_code': inventory_cp.returncode, 'stdout': inventory_cp.stdout[-1000:], 'stderr': inventory_cp.stderr[-1000:]}, ensure_ascii=False, indent=2))
        return 1
    try:
        payload = json.loads(cp.stdout)
    except json.JSONDecodeError as exc:
        print(json.dumps({'status': 'FAIL', 'step': 'parse_json', 'error': str(exc), 'stdout': cp.stdout[-1000:]}, ensure_ascii=False, indent=2))
        return 1
    cron_jobs = payload.get('cron', {}).get('jobs') or []
    product_batches = payload.get('product_worktree_batches', {}).get('batches') or []
    previews = [str((job.get('latest_output') or {}).get('preview') or '') for job in cron_jobs]
    sensitive_markers = ('api_key', 'secret', 'password', 'token', 'authorization', 'bearer ')
    checks = {
        'status_present': payload.get('status') in {'PASS', 'PASS_WITH_NOTES', 'NEEDS_REPAIR'},
        'dirty_tree_present': isinstance(payload.get('dirty_tree'), dict) and 'total' in payload['dirty_tree'],
        'repair_tasks_present': isinstance(payload.get('repair_tasks'), dict) and 'summary' in payload['repair_tasks'],
        'cron_present': isinstance(payload.get('cron'), dict) and 'jobs' in payload['cron'],
        'product_worktree_batches_present': isinstance(payload.get('product_worktree_batches'), dict) and bool(product_batches),
        'product_worktree_batches_have_actions': all(batch.get('action') for batch in product_batches),
        'quarantine_surfaces_as_notes': payload.get('status') != 'PASS' or not any(batch.get('status') == 'QUARANTINED' for batch in product_batches),
        'personal_cron_excluded': all(job.get('job_id') != '4d0eca6a6eac' for job in cron_jobs),
        'cron_preview_redacted': not any(marker in preview.lower() for preview in previews for marker in sensitive_markers),
        'degraded_status_fail_closed': payload.get('status') != 'PASS' or payload.get('dirty_tree', {}).get('total', 0) == 0,
        'evidence_written_json': (root / 'reports' / 'v-control-plane-status' / 'latest.json').exists(),
        'evidence_written_md': (root / 'reports' / 'v-control-plane-status' / 'latest.md').exists(),
        'dirty_inventory_json': (root / 'reports' / 'v-control-plane-status' / 'dirty-inventory.json').exists(),
        'dirty_inventory_md': (root / 'reports' / 'v-control-plane-status' / 'dirty-inventory.md').exists(),
    }
    ok = all(checks.values())
    result = {
        'status': 'PASS' if ok else 'FAIL',
        'checks': checks,
        'control_plane_status': payload.get('status'),
        'dirty_total': payload.get('dirty_tree', {}).get('total'),
        'repair_active': payload.get('repair_tasks', {}).get('summary', {}).get('active'),
        'cron_delivery_errors': len(payload.get('cron', {}).get('delivery_errors') or []),
        'product_worktree_batches': [(batch.get('batch'), batch.get('status'), batch.get('dirty_total')) for batch in product_batches],
        'evidence': payload.get('evidence'),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == 'json' else result)
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
