from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

TERMINAL_STATES = {"PASS", "PASS_WITH_NOTES", "NEEDS_HUMAN", "BLOCKED", "IGNORED", "MERGED"}


@dataclass(frozen=True)
class PRAutonomyInput:
    owner: str
    repo: str
    number: int | None
    action: str
    state: str
    draft: bool
    base_ref: str
    head_ref: str
    head_sha: str
    head_repo: str
    changed_files: list[str]
    check_runs: dict[str, str]
    labels: list[str]

    @property
    def repo_id(self) -> str:
        return f"{self.owner}/{self.repo}"


def load_policy(root: Path, policy_id: str) -> dict[str, Any]:
    path = root / "pr-autonomy-policies" / f"{policy_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"policy not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def normalize_github_pr_event(payload: dict[str, Any]) -> PRAutonomyInput:
    repo = payload.get("repository") or {}
    owner_obj = repo.get("owner") or {}
    pr = payload.get("pull_request") or {}
    base = pr.get("base") or {}
    head = pr.get("head") or {}
    head_repo_obj = head.get("repo") or {}
    return PRAutonomyInput(
        owner=str(owner_obj.get("login") or payload.get("owner") or ""),
        repo=str(repo.get("name") or payload.get("repo") or ""),
        number=pr.get("number") or payload.get("number"),
        action=str(payload.get("action") or ""),
        state=str(pr.get("state") or payload.get("state") or "open"),
        draft=bool(pr.get("draft") or payload.get("draft") or False),
        base_ref=str(base.get("ref") or payload.get("base_ref") or ""),
        head_ref=str(head.get("ref") or payload.get("head_ref") or ""),
        head_sha=str(head.get("sha") or payload.get("head_sha") or payload.get("sha") or ""),
        head_repo=str(head_repo_obj.get("full_name") or payload.get("head_repo") or ""),
        changed_files=[str(x) for x in payload.get("changed_files", [])],
        check_runs={str(k): str(v).lower() for k, v in (payload.get("check_runs") or {}).items()},
        labels=[str(x) for x in payload.get("labels", [])],
    )


def repo_policy(policy: dict[str, Any], repo_id: str) -> dict[str, Any] | None:
    for repo in policy.get("repositories", []):
        if repo.get("id") == repo_id:
            return repo
    return None


def _matches_any(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def classify_risk(event: PRAutonomyInput, repo_cfg: dict[str, Any]) -> dict[str, Any]:
    risk_cfg = repo_cfg.get("risk", {})
    changed = event.changed_files
    high = [p for p in changed if _matches_any(p, risk_cfg.get("high_globs", []))]
    medium = [p for p in changed if _matches_any(p, risk_cfg.get("medium_globs", []))]
    large_limit = int(risk_cfg.get("large_diff_file_limit", 20))
    if high:
        return {"level": "high", "reasons": ["high_risk_file_match"], "files": high}
    if len(changed) > large_limit:
        return {"level": "high", "reasons": ["large_diff"], "files": changed}
    if medium:
        return {"level": "medium", "reasons": ["medium_risk_file_match"], "files": medium}
    return {"level": "low", "reasons": [], "files": []}


def compute_next_action(event: PRAutonomyInput, policy: dict[str, Any], repair_attempts: int = 0) -> dict[str, Any]:
    defaults = policy.get("defaults", {})
    dry_run = bool(defaults.get("dry_run", True))
    repo_cfg = repo_policy(policy, event.repo_id)
    base = {
        "policy_id": policy.get("id"),
        "repo": event.repo_id,
        "pr": event.number,
        "head_sha": event.head_sha,
        "dry_run": dry_run,
        "actions": [],
    }

    if not repo_cfg:
        status = "IGNORED" if defaults.get("unknown_repo") == "ignored" else "BLOCKED"
        return {**base, "state": status, "terminal": True, "risk": "unknown", "reason": "repository is not allowlisted"}

    if event.action not in {"opened", "synchronize", "reopened", "ready_for_review", "closed"}:
        status = "IGNORED" if defaults.get("unknown_action") == "ignored" else "BLOCKED"
        return {**base, "state": status, "terminal": True, "risk": "unknown", "reason": f"unsupported action: {event.action}"}
    if event.state == "closed" or event.action == "closed":
        return {**base, "state": "IGNORED", "terminal": True, "risk": "unknown", "reason": "pull request is closed"}
    if event.base_ref not in repo_cfg.get("base_branches", []):
        return {**base, "state": "BLOCKED", "terminal": True, "risk": "unknown", "reason": f"base branch {event.base_ref!r} is not allowed"}
    if event.head_repo and event.head_repo != event.repo_id:
        return {**base, "state": "NEEDS_HUMAN", "terminal": True, "risk": "unknown", "reason": "fork PRs require human decision", "actions": ["COMMENT_ADVISORY", "REQUEST_HUMAN_REVIEW"]}
    if event.draft:
        return {**base, "state": "WAITING_FOR_AUTHOR", "terminal": False, "risk": "unknown", "reason": "pull request is draft", "actions": ["NOOP"]}
    if not event.changed_files:
        return {**base, "state": "NEEDS_HUMAN", "terminal": True, "risk": "unknown", "reason": "changed-file snapshot is required for risk classification", "actions": ["COMMENT_ADVISORY", "REQUEST_HUMAN_REVIEW"]}

    risk = classify_risk(event, repo_cfg)
    if risk["level"] == "high" and defaults.get("high_risk_requires_human", True):
        return {**base, "state": "NEEDS_HUMAN", "terminal": True, "risk": risk, "reason": "high-risk PR requires human decision", "actions": ["COMMENT_ADVISORY", "REQUEST_HUMAN_REVIEW"]}

    missing_checks = [name for name in repo_cfg.get("required_checks", []) if name not in event.check_runs]
    pending_checks = [name for name in repo_cfg.get("required_checks", []) if event.check_runs.get(name) in {"queued", "in_progress", "pending", "requested"}]
    failed_checks = [name for name in repo_cfg.get("required_checks", []) if event.check_runs.get(name) in {"failure", "failed", "error", "cancelled", "timed_out"}]
    if missing_checks or pending_checks:
        return {**base, "state": "WAITING_FOR_CHECKS", "terminal": False, "risk": risk, "reason": "required checks missing or pending", "missing_checks": missing_checks, "pending_checks": pending_checks, "actions": ["NOOP"]}
    if failed_checks:
        repair = repo_cfg.get("repair", {})
        if repair.get("enabled"):
            if not repair.get("execution_enabled", False):
                return {**base, "state": "BLOCKED", "terminal": True, "risk": risk, "reason": "repair execution is disabled", "failed_checks": failed_checks, "actions": ["COMMENT_ADVISORY"]}
            max_attempts = min(int(defaults.get("max_repair_attempts", 0)), int(repair.get("max_attempts", 0)))
            denied = [p for p in event.changed_files if _matches_any(p, repair.get("denied_globs", []))]
            allowed = [p for p in event.changed_files if _matches_any(p, repair.get("allowed_globs", []))]
            if repair_attempts >= max_attempts:
                return {**base, "state": "BLOCKED", "terminal": True, "risk": risk, "reason": "repair attempts exhausted", "failed_checks": failed_checks, "repair_attempts": repair_attempts, "max_repair_attempts": max_attempts, "actions": ["COMMENT_ADVISORY"]}
            if denied or len(allowed) != len(event.changed_files) or risk["level"] == "high" or risk["level"] not in repair.get("allowed_risks", ["low"]):
                return {**base, "state": "NEEDS_HUMAN", "terminal": True, "risk": risk, "reason": "repair is outside allowed policy scope", "failed_checks": failed_checks, "denied_files": denied, "actions": ["COMMENT_ADVISORY", "REQUEST_HUMAN_REVIEW"]}
            return {**base, "state": "NEEDS_REPAIR", "terminal": False, "risk": risk, "reason": "required checks failed and repair is enabled", "failed_checks": failed_checks, "repair_attempts": repair_attempts, "max_repair_attempts": max_attempts, "actions": ["COMMENT_ADVISORY", "CREATE_REPAIR_DISPATCH"]}
        return {**base, "state": "BLOCKED", "terminal": True, "risk": risk, "reason": "required checks failed and repair is disabled", "failed_checks": failed_checks, "actions": ["COMMENT_ADVISORY"]}

    merge = repo_cfg.get("merge", {})
    if not merge.get("auto_merge_enabled", False) or not defaults.get("auto_merge", {}).get("enabled", False):
        return {**base, "state": "READY_FOR_HUMAN", "terminal": True, "risk": risk, "reason": "all required checks pass; auto-merge disabled", "actions": ["COMMENT_ADVISORY", "REQUEST_HUMAN_REVIEW"]}

    allowed_risks = defaults.get("auto_merge", {}).get("allowed_risks", ["low"])
    if risk["level"] not in allowed_risks:
        return {**base, "state": "NEEDS_HUMAN", "terminal": True, "risk": risk, "reason": "risk exceeds auto-merge policy", "actions": ["COMMENT_ADVISORY", "REQUEST_HUMAN_REVIEW"]}

    action = "MERGE_PR" if not dry_run else "MERGE_PR_PLANNED_ONLY"
    return {**base, "state": "READY_TO_MERGE", "terminal": False, "risk": risk, "reason": "eligible for policy-gated auto-merge", "actions": ["COMMENT_ADVISORY", action]}


def dispatch_payload(root: Path, policy_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    policy = load_policy(root, policy_id)
    event = normalize_github_pr_event(payload)
    repair_attempts = int(payload.get("repair_attempts", 0) or 0)
    return compute_next_action(event, policy, repair_attempts=repair_attempts)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m selfcheck.pr_autonomy")
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="github-pr-autonomy-v-workspace")
    parser.add_argument("--payload-file", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)

    root = Path(args.root)
    payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    result = dispatch_payload(root, args.policy, payload)
    text = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
