#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT_FOR_IMPORT = Path(__file__).resolve().parents[1]
if str(ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(ROOT_FOR_IMPORT))

from selfcheck.pr_autonomy import dispatch_payload, load_policy, repo_policy  # noqa: E402

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def run(args: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def gh_json(root: Path, args: list[str], default: Any) -> Any:
    cp = run(["gh", *args], root, timeout=120)
    if cp.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {cp.stderr[-500:]}")
    text = cp.stdout.strip()
    return json.loads(text) if text else default


def matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def state_path(root: Path, repo: str, pr: int) -> Path:
    safe_repo = repo.replace("/", "__")
    return root / "reports" / "github-pr-autonomy-live-webhook" / "repair-state" / f"{safe_repo}__{pr}.json"


def load_attempts(root: Path, repo: str, pr: int) -> int:
    path = state_path(root, repo, pr)
    if not path.exists():
        return 0
    try:
        return int((json.loads(path.read_text(encoding="utf-8")) or {}).get("attempts") or 0)
    except Exception:
        return 0


def save_attempt(root: Path, repo: str, pr: int, data: dict[str, Any]) -> None:
    path = state_path(root, repo, pr)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def current_payload(root: Path, repo: str, pr_number: int) -> dict[str, Any]:
    pr = gh_json(root, ["api", f"repos/{repo}/pulls/{pr_number}"], {})
    files = gh_json(root, ["api", f"repos/{repo}/pulls/{pr_number}/files", "--paginate"], [])
    sha = ((pr.get("head") or {}).get("sha") or "")
    checks = {}
    if sha:
        check_runs = gh_json(root, ["api", f"repos/{repo}/commits/{sha}/check-runs", "--jq", ".check_runs"], [])
        for item in check_runs or []:
            name = str(item.get("name") or "")
            if not name:
                continue
            status = str(item.get("status") or "").lower()
            conclusion = str(item.get("conclusion") or "").lower()
            checks[name] = conclusion if status == "completed" else status or "pending"
        statuses = gh_json(root, ["api", f"repos/{repo}/commits/{sha}/status", "--jq", ".statuses"], [])
        for item in statuses or []:
            context = str(item.get("context") or "")
            if context and context not in checks:
                checks[context] = str(item.get("state") or "").lower()
    return {
        "action": "synchronize",
        "repository": (pr.get("base") or {}).get("repo") or {},
        "pull_request": pr,
        "number": pr_number,
        "head_sha": sha,
        "changed_files": [str(x.get("filename")) for x in files if x.get("filename")],
        "check_runs": checks,
        "labels": [str(x.get("name")) for x in pr.get("labels", []) if x.get("name")],
    }


def apply_markdown_marker_fixer(worktree: Path, files: list[str]) -> list[str]:
    changed: list[str] = []
    for rel in files:
        if not rel.endswith(".md"):
            continue
        path = worktree / rel
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        new = text.replace("PR_AUTONOMY_REPAIR_FAIL", "PR_AUTONOMY_REPAIR_FIXED")
        new = new.replace("<!-- pr-autonomy-repair:fail -->", "<!-- pr-autonomy-repair:fixed -->")
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(rel)
    return changed


def apply_gofmt_fixer(worktree: Path, files: list[str]) -> list[str]:
    go_files = [rel for rel in files if rel.endswith(".go") and (worktree / rel).exists()]
    if not go_files:
        return []
    gofmt = shutil.which("gofmt") or "/usr/local/go/bin/gofmt"
    if not Path(gofmt).exists():
        raise RuntimeError("gofmt is not available in service PATH")
    before = {rel: (worktree / rel).read_text(encoding="utf-8") for rel in go_files}
    cp = run([gofmt, "-w", *go_files], worktree)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-500:])
    return [rel for rel in go_files if (worktree / rel).read_text(encoding="utf-8") != before[rel]]


def diff_files(worktree: Path) -> list[str]:
    cp = run(["git", "diff", "--name-only"], worktree)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-500:])
    return [line.strip() for line in cp.stdout.splitlines() if line.strip()]


def diff_text(worktree: Path) -> str:
    cp = run(["git", "diff", "--cached"], worktree)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-500:])
    return cp.stdout


def secret_scan(text: str) -> list[str]:
    hits = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def ensure_worktree(root: Path, repo: str, pr: dict[str, Any], base_dir: Path) -> Path:
    owner, name = repo.split("/", 1)
    worktree = base_dir / owner / name
    if worktree.exists() and not (worktree / ".git").exists():
        shutil.rmtree(worktree)
    if not worktree.exists():
        worktree.parent.mkdir(parents=True, exist_ok=True)
        cp = run(["gh", "repo", "clone", repo, str(worktree)], root, timeout=300)
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr[-1000:])
    if repo.startswith("mahama-11/"):
        cp = run(["git", "remote", "set-url", "origin", f"github.com-mahama:{repo}.git"], worktree)
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr[-1000:])
    cp = run(["git", "fetch", "origin", "--prune"], worktree, timeout=240)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-1000:])
    head_ref = str((pr.get("head") or {}).get("ref") or "")
    if not head_ref:
        raise RuntimeError("missing PR head ref")
    cp = run(["git", "checkout", "-B", f"pr-autonomy-{pr.get('number')}", f"origin/{head_ref}"], worktree)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-1000:])
    cp = run(["git", "reset", "--hard", f"origin/{head_ref}"], worktree)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-1000:])
    return worktree


def repair(root: Path, policy_id: str, repo: str, pr_number: int, expected_sha: str | None, report_path: Path) -> dict[str, Any]:
    lock_path = state_path(root, repo, pr_number).with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        return _repair_locked(root, policy_id, repo, pr_number, expected_sha, report_path)


def _repair_locked(root: Path, policy_id: str, repo: str, pr_number: int, expected_sha: str | None, report_path: Path) -> dict[str, Any]:
    policy = load_policy(root, policy_id)
    payload = current_payload(root, repo, pr_number)
    pr = payload.get("pull_request") or {}
    live_sha = str(payload.get("head_sha") or "")
    attempts = load_attempts(root, repo, pr_number)
    payload["repair_attempts"] = attempts
    decision = dispatch_payload(root, policy_id, payload)
    repo_cfg = repo_policy(policy, repo)
    if not repo_cfg:
        raise RuntimeError("repo is not allowlisted")
    repair_cfg = repo_cfg.get("repair", {})
    if not repair_cfg.get("execution_enabled", False):
        raise RuntimeError("repair execution is disabled by policy")
    if decision.get("state") != "NEEDS_REPAIR":
        result = {"status": "SKIPPED", "reason": "decision is not NEEDS_REPAIR", "decision": decision, "attempts": attempts}
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return result
    if expected_sha and live_sha != expected_sha:
        raise RuntimeError("PR head changed before repair")
    if pr.get("draft") or pr.get("state") != "open":
        raise RuntimeError("PR is not open and ready")
    if ((pr.get("head") or {}).get("repo") or {}).get("full_name") != repo:
        raise RuntimeError("fork PR repair is not allowed")
    changed_files = payload.get("changed_files") or []
    allowed = repair_cfg.get("allowed_globs", [])
    denied = repair_cfg.get("denied_globs", [])
    if any(matches_any(path, denied) for path in changed_files):
        raise RuntimeError("changed files include denied repair paths")
    if not all(matches_any(path, allowed) for path in changed_files):
        raise RuntimeError("changed files are outside repair allowlist")
    risk = decision.get("risk") if isinstance(decision.get("risk"), dict) else {}
    if (risk.get("level") or "unknown") not in repair_cfg.get("allowed_risks", ["low"]):
        raise RuntimeError("repair risk level is outside allowed repair risks")
    fixers = repair_cfg.get("fixers") or ["markdown-marker"]
    save_attempt(root, repo, pr_number, {
        "status": "STARTED",
        "repo": repo,
        "pr": pr_number,
        "attempts": attempts + 1,
        "attempts_before": attempts,
        "attempts_after": attempts + 1,
        "head_sha": live_sha,
        "fixers": fixers,
    })
    base_dir = root / ".worktrees" / "github-pr-autonomy-repair"
    worktree = ensure_worktree(root, repo, pr, base_dir)
    fixed: list[str] = []
    if "markdown-marker" in fixers:
        fixed.extend(apply_markdown_marker_fixer(worktree, changed_files))
    if "gofmt" in fixers:
        fixed.extend(apply_gofmt_fixer(worktree, changed_files))
    changed_after = diff_files(worktree)
    if not changed_after:
        raise RuntimeError("no deterministic repair was applicable")
    if set(changed_after) - set(changed_files):
        raise RuntimeError("repair changed files outside PR diff")
    if any(matches_any(path, denied) for path in changed_after) or not all(matches_any(path, allowed) for path in changed_after):
        raise RuntimeError("repair diff violates allowlist/denylist")
    cp = run(["git", "diff", "--check"], worktree)
    if cp.returncode != 0:
        raise RuntimeError(cp.stdout[-500:] + cp.stderr[-500:])
    cp = run(["git", "add", *changed_after], worktree)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-500:])
    diff = diff_text(worktree)
    hits = secret_scan(diff)
    if hits:
        raise RuntimeError("secret scan blocked repair diff")
    latest = current_payload(root, repo, pr_number)
    if str(latest.get("head_sha") or "") != live_sha:
        raise RuntimeError("PR head changed before repair push")
    cp = run(["git", "commit", "-m", f"fix: automated PR autonomy repair (#{pr_number})"], worktree)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-1000:])
    new_sha = run(["git", "rev-parse", "HEAD"], worktree).stdout.strip()
    head_ref = str((pr.get("head") or {}).get("ref") or "")
    cp = run(["git", "push", "origin", f"HEAD:{head_ref}"], worktree, timeout=300)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-1000:])
    result = {
        "status": "PASS",
        "repo": repo,
        "pr": pr_number,
        "attempts": attempts + 1,
        "attempts_before": attempts,
        "attempts_after": attempts + 1,
        "old_head_sha": live_sha,
        "new_head_sha": new_sha,
        "fixed_files": changed_after,
        "fixers": fixers,
        "decision": decision,
    }
    save_attempt(root, repo, pr_number, result)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="github-pr-autonomy-v-workspace")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--expected-sha")
    parser.add_argument("--report", default="reports/github-pr-autonomy-live-webhook/repair/latest-repair.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    result = repair(root, args.policy, args.repo, args.pr, args.expected_sha, root / args.report)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") in {"PASS", "SKIPPED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
