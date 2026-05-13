#!/usr/bin/env python3
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    script = Path(__file__).resolve().parent / 'frontend_quality_gate.py'
    control_root = script.parent.parent
    ap = argparse.ArgumentParser(description='Run the generic frontend quality gate against the V workspace adapter.')
    ap.add_argument('--project-root', default='/root/work/v', help='V workspace/project root containing .hermes workflows')
    ap.add_argument('--workflow', required=True, help='Workflow directory under the V project root')
    ap.add_argument('--risk', choices=['C','D'], default='D')
    ap.add_argument('--format', choices=['json','text'], default='text')
    args = ap.parse_args()
    cmd = [
        sys.executable,
        str(script),
        '--root', str(Path(args.project_root).resolve()),
        '--base-root', str(control_root.resolve()),
        '--workflow', args.workflow,
        '--risk', args.risk,
        '--format', args.format,
    ]
    return subprocess.run(cmd).returncode


if __name__ == '__main__':
    raise SystemExit(main())
