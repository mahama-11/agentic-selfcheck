#!/usr/bin/env python3
"""Summarize V product-side dirty worktree batches without treating them as ready-to-merge.

This is a lightweight control-plane helper for the staged cleanup workflow:
- Batch B: environment/dependency noise
- Batch C: CrossPlanet/List Strategy quarantined worktrees
- Batch D: Ecommerce V1 listing immutability worktrees

It intentionally does not modify product repos.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

BATCHES = {
    "batch_b_env": [
        "/root/work/v/platform-frontend",
        "/root/work/v/menu-frontend",
        "/root/work/v/kyc-backend",
        "/root/work/v/kyc-frontend",
    ],
    "batch_c_crossplanet": [
        "/root/work/v-worktrees/crossplanet-listing-strategy-backend",
        "/root/work/v-worktrees/crossplanet-listing-strategy-frontend",
    ],
    "batch_d_v1_listing": [
        "/root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-backend",
        "/root/work/v-worktrees/ecommerce-v1-listing-immutability/ecommerce-frontend",
    ],
}


def run_git(repo: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(["git", "-C", str(repo), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    return proc.returncode, proc.stdout.strip()


def summarize_repo(repo_text: str) -> dict[str, Any]:
    repo = Path(repo_text)
    exists = repo.exists()
    item: dict[str, Any] = {"repo": repo_text, "exists": exists}
    if not exists:
        item.update({"status": "MISSING", "dirty_count": 0, "files": []})
        return item
    code, status = run_git(repo, "status", "--short")
    if code != 0:
        item.update({"status": "GIT_ERROR", "dirty_count": 0, "files": [], "error": status})
        return item
    files = [line.strip() for line in status.splitlines() if line.strip()]
    log_code, head = run_git(repo, "log", "-1", "--oneline")
    stat_code, stat = run_git(repo, "diff", "--stat")
    item.update(
        {
            "status": "DIRTY" if files else "CLEAN",
            "dirty_count": len(files),
            "files": files,
            "head": head if log_code == 0 else "",
            "diff_stat": stat if stat_code == 0 else "",
        }
    )
    return item


def classify_batch(batch: str, repos: list[dict[str, Any]]) -> dict[str, Any]:
    dirty = sum(int(repo.get("dirty_count", 0)) for repo in repos)
    if batch == "batch_b_env":
        status = "PASS" if dirty == 0 else "NEEDS_REPAIR"
        action = "keep clean; commit only explicit toolchain scripts"
    elif batch == "batch_c_crossplanet":
        status = "QUARANTINED" if dirty else "CLEAN"
        action = "do not merge product worktrees until CrossPlanet gates are repaired and pass"
    elif batch == "batch_d_v1_listing":
        status = "QUARANTINED" if dirty else "CLEAN"
        action = "treat as active large slice; require dedicated listing/export gate before merge"
    else:
        status = "UNKNOWN"
        action = "inspect"
    return {"batch": batch, "status": status, "dirty_total": dirty, "action": action, "repos": repos}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=["json", "text"], default="text")
    args = parser.parse_args()
    result = [classify_batch(name, [summarize_repo(repo) for repo in repos]) for name, repos in BATCHES.items()]
    if args.format == "json":
        print(json.dumps({"status": "PASS", "batches": result}, ensure_ascii=False, indent=2))
    else:
        for batch in result:
            print(f"{batch['batch']}: {batch['status']} dirty_total={batch['dirty_total']} action={batch['action']}")
            for repo in batch["repos"]:
                print(f"  - {repo['repo']}: {repo['status']} dirty={repo.get('dirty_count', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
