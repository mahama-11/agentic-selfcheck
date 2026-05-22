#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    cp = subprocess.run(['scripts/v_product_worktree_batch_status.py', '--format', 'json'], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if cp.returncode != 0:
        print(cp.stdout[-1000:])
        print(cp.stderr[-1000:], file=sys.stderr)
        return 1
    data = json.loads(cp.stdout)
    batches = {b['batch']: b for b in data.get('batches', [])}
    required = ['batch_b_env', 'batch_c_crossplanet', 'batch_d_v1_listing']
    missing = [name for name in required if name not in batches]
    if missing:
        print(json.dumps({'status': 'FAIL', 'missing': missing}, ensure_ascii=False))
        return 1
    if batches['batch_b_env']['status'] != 'PASS':
        print(json.dumps({'status': 'FAIL', 'batch_b_env': batches['batch_b_env']}, ensure_ascii=False))
        return 1
    for name in ['batch_c_crossplanet', 'batch_d_v1_listing']:
        if batches[name]['status'] not in {'QUARANTINED', 'CLEAN'}:
            print(json.dumps({'status': 'FAIL', 'batch': batches[name]}, ensure_ascii=False))
            return 1
        if not batches[name].get('action'):
            print(json.dumps({'status': 'FAIL', 'missing_action': name}, ensure_ascii=False))
            return 1
    print(json.dumps({'status': 'PASS', 'batches': [(k, batches[k]['status'], batches[k]['dirty_total']) for k in required]}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
