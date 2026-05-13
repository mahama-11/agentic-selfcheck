#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / '.git' / 'hooks'

PRE_PUSH = """#!/usr/bin/env bash
set -euo pipefail
cd {root}
python3 scripts/continuous_governance_trigger.py --root . --git-mode pre-push --source git-hook --timeout 300
""".format(root=ROOT)
POST_MERGE = """#!/usr/bin/env bash
set -euo pipefail
cd {root}
python3 scripts/continuous_governance_trigger.py --root . --git-mode head --source git-hook --timeout 300 || true
""".format(root=ROOT)

def write_hook(name: str, content: str):
    HOOKS.mkdir(parents=True, exist_ok=True)
    path = HOOKS / name
    if path.exists() and 'continuous_governance_trigger.py' not in path.read_text(encoding='utf-8', errors='ignore'):
        backup = path.with_suffix(path.suffix + '.pre-continuous-governance.bak')
        backup.write_text(path.read_text(encoding='utf-8', errors='ignore'), encoding='utf-8')
    path.write_text(content, encoding='utf-8')
    os.chmod(path, 0o755)
    return path

def main():
    for p in [write_hook('pre-push', PRE_PUSH), write_hook('post-merge', POST_MERGE)]:
        print(f'installed {p}')

if __name__ == '__main__':
    main()
