#!/usr/bin/env python3
from __future__ import annotations
import os
import subprocess
from pathlib import Path

SELF_ROOT = Path('/root/work/agentic-selfcheck')
V_ROOT = Path('/root/work/v')
REPOS = [
    'platform-backend', 'ecommerce-backend', 'menu-backend', 'kyc-backend',
    'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend',
]


def discover_repos() -> list[Path]:
    """Return canonical V repos plus any existing isolated worktrees/repos."""
    repos: list[Path] = []
    seen: set[Path] = set()
    for name in REPOS:
        repo = V_ROOT / name
        if repo.exists() and repo not in seen:
            repos.append(repo)
            seen.add(repo)
    for git_path in V_ROOT.glob('*/.git'):
        repo = git_path.parent
        if repo.exists() and repo not in seen:
            repos.append(repo)
            seen.add(repo)
    return repos


def hook_content(repo: Path, name: str) -> str:
    mode = 'pre-push' if name == 'pre-push' else 'head'
    # pre-push is the hard automatic quality gate: run selected business gates so
    # engineers/agents cannot forget Ecommerce-specific QA before code leaves a repo.
    business = ' --run-business-gates' if name == 'pre-push' else ''
    # The standalone frontend before-implementation gate is still too broad for
    # repository hooks (it can classify copy/i18n/page cleanup as C-risk and
    # block every push). Keep business QA automatic now; mature frontend workflow
    # enforcement behind its own selector before making it hook-blocking.
    frontend_enforcement = ' --no-enforce-frontend-implementation'
    suffix = '' if name == 'pre-push' else ' || true'
    return f"""#!/usr/bin/env bash
set -euo pipefail
repo="$(git rev-parse --show-toplevel)"
python3 {SELF_ROOT}/scripts/v_continuous_governance_trigger.py --repo-root "$repo" --git-mode {mode} --source git-hook --timeout 300{business}{frontend_enforcement}{suffix}
"""


def hook_dir(repo: Path) -> Path | None:
    """Resolve hooks directory for normal repos and git-worktree .git files."""
    try:
        proc = subprocess.run(
            ['git', 'rev-parse', '--git-path', 'hooks'],
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=10,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            p = Path(proc.stdout.strip())
            return p if p.is_absolute() else (repo / p)
    except Exception:
        pass
    fallback = repo / '.git' / 'hooks'
    if fallback.parent.exists() and fallback.parent.is_dir():
        return fallback
    return None


def write_hook(repo: Path, name: str) -> Path:
    hooks = hook_dir(repo)
    if hooks is None:
        raise RuntimeError(f'cannot resolve git hooks dir for {repo}')
    path = hooks / name
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
    for repo in discover_repos():
        if not (repo / '.git').exists():
            skipped.append(str(repo))
            continue
        installed.append(str(write_hook(repo, 'pre-push')))
        installed.append(str(write_hook(repo, 'post-merge')))
    print({'installed': installed, 'skipped': skipped})


if __name__ == '__main__':
    main()
