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


def evidence_if_exists(path: str) -> dict[str, str] | None:
    p = Path(path)
    if not p.exists():
        return None
    return {"path": str(p), "kind": "batch_quarantine_exit_classification"}


def latest_crossplanet_same_run_gate(selfcheck_root: Path = Path("/root/work/agentic-selfcheck")) -> dict[str, str] | None:
    """Return latest repaired CrossPlanet same-run gate evidence, if it passed.

    Batch C used to be classified only from a stale quarantine-exit markdown file.
    The repaired gate writes normal SelfCheck loop/verifier evidence, so the control
    plane should surface that same-run root-aware result instead of continuing to
    describe the batch as awaiting a dedicated repair plan.
    """
    loop_dir = selfcheck_root / "reports/loops/crossplanet-listing-strategy-gate-repair"
    candidates = sorted(loop_dir.glob("loop-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("status") not in {"PASS", "PASS_WITH_NOTES"}:
            continue
        verifiers = payload.get("verifiers") or []
        if not any(
            item.get("id") == "crossplanet-listing-strategy-gate-repair-static"
            and item.get("status") == "PASS"
            and item.get("ok") is True
            for item in verifiers
        ):
            continue
        return {
            "path": str(path),
            "kind": "selfcheck_same_run_root_aware_gate",
            "status": str(payload.get("status")),
        }
    return None


def classify_batch(batch: str, repos: list[dict[str, Any]]) -> dict[str, Any]:
    dirty = sum(int(repo.get("dirty_count", 0)) for repo in repos)
    evidence: dict[str, str] | None = None
    blocking_notes: list[str] = []
    if batch == "batch_b_env":
        status = "PASS" if dirty == 0 else "NEEDS_REPAIR"
        action = "keep clean; commit only explicit toolchain scripts"
    elif batch == "batch_c_crossplanet":
        evidence = latest_crossplanet_same_run_gate() or evidence_if_exists(
            "/root/work/v/reports/crossplanet-listing-strategy-input/2026-05-24-batch-c/quarantine-exit-classification.md"
        )
        if dirty and evidence and evidence.get("kind") == "selfcheck_same_run_root_aware_gate":
            status = "HITL_BLOCKED_WITH_REPAIRED_GATES"
            action = "do not merge; repaired same-run CrossPlanet gate passed, owner approval is still required"
            blocking_notes = [
                "repaired CrossPlanet gate ran backend/frontend checks from explicit roots in the same SelfCheck loop",
                "human approval required before merging worktrees or deploying product changes",
            ]
        elif dirty and evidence:
            status = "QUARANTINED_WITH_DEDICATED_REPAIR_PLAN"
            action = "do not merge; backend/frontend checks passed but repaired same-run CrossPlanet merge gate is still required"
            blocking_notes = [
                "only stale quarantine-exit classification evidence is available",
                "human approval required before promoting archived CrossPlanet gates or merging worktrees",
            ]
        else:
            status = "QUARANTINED" if dirty else "CLEAN"
            action = "do not merge product worktrees until CrossPlanet gates are repaired and pass"
    elif batch == "batch_d_v1_listing":
        evidence = evidence_if_exists(
            "/root/work/agentic-selfcheck/reports/ecommerce-v1-listing-export-gate/batch-d-quarantine-exit-2026-05-24.md"
        )
        if dirty and evidence:
            status = "HITL_BLOCKED_WITH_VERIFIED_GATES"
            action = "do not merge; automated gates passed, owner decision needed for gate-state/deploy policy"
            blocking_notes = [
                "listing/export static gate still reports quarantine merge_state",
                "package-manager lock drift was resolved by removing accidental untracked pnpm-lock.yaml and keeping npm/package-lock as source of truth",
                "no production deploy/public bundle approval was requested or performed",
            ]
        else:
            status = "QUARANTINED" if dirty else "CLEAN"
            action = "treat as active large slice; require dedicated listing/export gate before merge"
    else:
        status = "UNKNOWN"
        action = "inspect"
    result = {"batch": batch, "status": status, "dirty_total": dirty, "action": action, "repos": repos}
    if evidence:
        result["evidence"] = evidence
    if blocking_notes:
        result["blocking_notes"] = blocking_notes
    return result


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
