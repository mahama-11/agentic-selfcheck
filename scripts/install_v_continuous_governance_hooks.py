#!/usr/bin/env python3
from __future__ import annotations
import os
from pathlib import Path

SELF_ROOT = Path('/root/work/agentic-selfcheck')
V_ROOT = Path('/root/work/v')
REPOS = [
    'platform-backend', 'ecommerce-backend', 'menu-backend', 'kyc-backend',
    'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend',
]


def hook_content(repo: Path, name: str) -> str:
    mode = 'pre-push' if name == 'pre-push' else 'head'
    suffix = '' if name == 'pre-push' else ' || true'
    return f"""#!/usr/bin/env bash
set -euo pipefail
python3 {SELF_ROOT}/scripts/v_continuous_governance_trigger.py --repo-root {repo} --git-mode {mode} --source git-hook --timeout 300{suffix}
"""


def write_hook(repo: Path, name: str) -> Path:
    path = repo / '.git' / 'hooks' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and 'v_continuous_governance_trigger.py' not in path.read_text(encoding='utf-8', errors='ignore'):
        backup = path.with_suffix(path.suffix + '.pre-v-governance.bak')
        backup.write_text(path.read_text(encoding='utf-8', errors='ignore'), encoding='utf-8')
    path.write_text(hook_content(repo, name), encoding='utf-8')
    os.chmod(path, 0o755)
    return path


def main() -> None:
    installed = []
    skipped = []
    for name in REPOS:
        repo = V_ROOT / name
        if not (repo / '.git').exists():
            skipped.append(str(repo))
            continue
        installed.append(str(write_hook(repo, 'pre-push')))
        installed.append(str(write_hook(repo, 'post-merge')))
    print({'installed': installed, 'skipped': skipped})


if __name__ == '__main__':
    main()
