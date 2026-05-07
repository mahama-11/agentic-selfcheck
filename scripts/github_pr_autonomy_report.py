#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT_FOR_IMPORT = Path(__file__).resolve().parents[1]
if str(ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(ROOT_FOR_IMPORT))

from selfcheck.pr_autonomy import dispatch_payload
import yaml


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=60)


def desired_labels(decision: dict) -> list[str]:
    state = str(decision.get("state") or "UNKNOWN")
    risk = decision.get("risk")
    risk_level = risk.get("level") if isinstance(risk, dict) else "unknown"
    labels = ["ai-reviewed", f"ai-state:{state.lower().replace('_', '-')}"]
    if risk_level:
        labels.append(f"risk:{risk_level}")
    if state in {"NEEDS_HUMAN", "BLOCKED"}:
        labels.append("ai-needs-human")
    elif state == "WAITING_FOR_CHECKS":
        labels.append("ai-waiting-checks")
    elif state == "NEEDS_REPAIR":
        labels.append("ai-needs-repair")
    return labels


def ensure_labels(repo: str, labels: list[str], cwd: Path) -> list[dict]:
    applied: list[dict] = []
    for label in labels:
        color = "ededed"
        if label.startswith("risk:high") or label in {"ai-needs-human", "ai-needs-repair"}:
            color = "d73a4a"
        elif label.startswith("risk:medium") or label == "ai-waiting-checks":
            color = "fbca04"
        elif label.startswith("risk:low") or label == "ai-reviewed":
            color = "0e8a16"
        cp = run(["gh", "label", "create", label, "--repo", repo, "--color", color, "--force"], cwd=cwd)
        applied.append({"action": "ensure_label", "label": label, "exit_code": cp.returncode, "stderr_tail": cp.stderr[-300:]})
    return applied


def current_labels(repo: str, pr: int, cwd: Path) -> list[str]:
    cp = run(["gh", "pr", "view", str(pr), "--repo", repo, "--json", "labels", "--jq", ".[0]"], cwd=cwd)
    # The jq above intentionally returns null on old gh versions; fall back to JSON parsing.
    cp = run(["gh", "pr", "view", str(pr), "--repo", repo, "--json", "labels"], cwd=cwd)
    if cp.returncode != 0:
        return []
    try:
        data = json.loads(cp.stdout)
    except Exception:
        return []
    return [str(x.get("name")) for x in data.get("labels", []) if x.get("name")]


def reconcile_labels(repo: str, pr: int, labels: list[str], cwd: Path) -> list[dict]:
    applied = ensure_labels(repo, labels, cwd)
    managed_prefixes = ("ai-state:", "risk:")
    managed_exact = {"ai-waiting-checks", "ai-needs-human", "ai-needs-repair"}
    existing = current_labels(repo, pr, cwd)
    remove = [x for x in existing if (x.startswith(managed_prefixes) or x in managed_exact) and x not in labels]
    for label in remove:
        cp = run(["gh", "issue", "edit", str(pr), "--repo", repo, "--remove-label", label], cwd=cwd)
        applied.append({"action": "remove_label", "label": label, "exit_code": cp.returncode, "stderr_tail": cp.stderr[-300:]})
    cp = run(["gh", "issue", "edit", str(pr), "--repo", repo, "--add-label", ",".join(labels)], cwd=cwd)
    applied.append({"action": "labels", "labels": labels, "exit_code": cp.returncode, "stderr_tail": cp.stderr[-500:]})
    if cp.returncode != 0:
        raise SystemExit(cp.returncode)
    return applied


def post_or_update_comment(repo: str, pr: int, body: str, cwd: Path) -> subprocess.CompletedProcess:
    marker = "## AI PR Autonomy Decision"
    cp = run(["gh", "api", f"repos/{repo}/issues/{pr}/comments", "--jq", f".[] | select(.body | contains(\"{marker}\")) | .id"], cwd=cwd)
    if cp.returncode == 0:
        ids = [line.strip() for line in cp.stdout.splitlines() if line.strip()]
        if ids:
            return run(["gh", "api", "--method", "PATCH", f"repos/{repo}/issues/comments/{ids[-1]}", "-f", f"body={body}"], cwd=cwd)
    return run(["gh", "pr", "comment", str(pr), "--repo", str(repo), "--body", body], cwd=cwd)


def gh_json(root: Path, args: list[str], default):
    cp = run(["gh", *args], cwd=root)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-500:])
    text = cp.stdout.strip()
    return json.loads(text) if text else default


def live_payload(root: Path, repo: str, pr: int) -> dict:
    pr_data = gh_json(root, ["api", f"repos/{repo}/pulls/{pr}"], {})
    files = gh_json(root, ["api", f"repos/{repo}/pulls/{pr}/files", "--paginate"], [])
    sha = ((pr_data.get("head") or {}).get("sha") or "")
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
        "repository": (pr_data.get("base") or {}).get("repo") or {},
        "pull_request": pr_data,
        "number": pr,
        "head_sha": sha,
        "changed_files": [str(x.get("filename")) for x in files if x.get("filename")],
        "check_runs": checks,
        "labels": [str(x.get("name")) for x in pr_data.get("labels", []) if x.get("name")],
    }


def policy_merge_method(root: Path, policy_id: str, repo: str) -> str:
    policy_path = root / "pr-autonomy-policies" / f"{policy_id}.yaml"
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    method = ((policy.get("defaults") or {}).get("auto_merge") or {}).get("method") or "squash"
    for item in policy.get("repositories", []):
        if item.get("id") == repo:
            allowed = ((item.get("merge") or {}).get("allowed_methods") or [method])
            if method not in allowed:
                raise RuntimeError("configured merge method is not allowed for repo")
            if (item.get("merge") or {}).get("require_human_approval"):
                raise RuntimeError("repo merge policy still requires human approval")
            break
    return str(method)


def perform_policy_merge(root: Path, policy_id: str, repo: str, pr: int, original_decision: dict) -> dict:
    payload = live_payload(root, repo, pr)
    live_decision = dispatch_payload(root, policy_id, payload)
    original_sha = str(original_decision.get("head_sha") or "")
    live_sha = str(live_decision.get("head_sha") or payload.get("head_sha") or "")
    if original_sha and live_sha != original_sha:
        raise RuntimeError("PR head changed before merge")
    pr_data = payload.get("pull_request") or {}
    if pr_data.get("state") != "open" or pr_data.get("draft"):
        raise RuntimeError("PR is not open and ready for merge")
    if ((pr_data.get("head") or {}).get("repo") or {}).get("full_name") != repo:
        raise RuntimeError("fork PR auto-merge is not allowed")
    if live_decision.get("state") != "READY_TO_MERGE" or "MERGE_PR" not in live_decision.get("actions", []):
        raise RuntimeError("live policy decision is not mergeable")
    method = policy_merge_method(root, policy_id, repo)
    args = ["gh", "pr", "merge", str(pr), "--repo", str(repo), f"--{method}", "--delete-branch"]
    cp = run(args, cwd=root)
    return {"action": "merge", "method": method, "exit_code": cp.returncode, "stderr_tail": cp.stderr[-500:], "stdout_tail": cp.stdout[-500:], "live_decision": live_decision}


def markdown_summary(decision: dict) -> str:
    risk = decision.get("risk")
    if isinstance(risk, dict):
        risk_text = f"{risk.get('level')} ({', '.join(risk.get('reasons') or []) or 'no explicit risk reason'})"
    else:
        risk_text = str(risk)
    actions = ", ".join(decision.get("actions") or []) or "none"
    return f"""## AI PR Autonomy Decision

- State: `{decision.get('state')}`
- Terminal: `{decision.get('terminal')}`
- Risk: `{risk_text}`
- Reason: {decision.get('reason')}
- Planned actions: `{actions}`
- Dry run: `{decision.get('dry_run')}`

This report is generated by Agentic SelfCheck. Secrets are never included in this comment.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="github-pr-autonomy-v-workspace")
    parser.add_argument("--payload-file", required=True)
    parser.add_argument("--repo", help="owner/repo for GitHub reporting")
    parser.add_argument("--pr", type=int, help="PR number for GitHub reporting")
    parser.add_argument("--apply", action="store_true", help="Apply GitHub comment/check reporting. Default is dry-run only.")
    parser.add_argument("--allow-merge", action="store_true", help="Allow actual merge if policy decision is READY_TO_MERGE. Requires --apply.")
    parser.add_argument("--labels", action="store_true", help="Apply PR labels alongside comment/status when --apply is set.")
    parser.add_argument("--report", default="reports/github-pr-autonomy/github-pr-autonomy-report.json")
    args = parser.parse_args()

    root = Path(args.root)
    payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    decision = dispatch_payload(root, args.policy, payload)
    repo = args.repo or decision.get("repo")
    pr = args.pr or decision.get("pr")
    comment = markdown_summary(decision)
    applied: list[dict] = []

    if args.apply:
        if not repo or not pr:
            raise SystemExit("--repo and --pr are required for --apply")
        cp = post_or_update_comment(str(repo), int(pr), comment, root)
        applied.append({"action": "comment_upsert", "exit_code": cp.returncode, "stderr_tail": cp.stderr[-500:]})
        if cp.returncode != 0:
            raise SystemExit(cp.returncode)
        state = str(decision.get("state"))
        conclusion = "success" if state in {"PASS", "PASS_WITH_NOTES", "READY_FOR_HUMAN", "READY_TO_MERGE"} else "failure" if state == "BLOCKED" else "neutral"
        sha = str(decision.get("head_sha") or payload.get("head_sha") or "")
        if sha:
            cp = run([
                "gh", "api", f"repos/{repo}/statuses/{sha}",
                "-f", "state=success" if conclusion == "success" else "state=failure" if conclusion == "failure" else "state=pending",
                "-f", "context=AI Review / PR Autonomy",
                "-f", f"description={state}: {str(decision.get('reason'))[:120]}",
            ], cwd=root)
            applied.append({"action": "status", "exit_code": cp.returncode, "stderr_tail": cp.stderr[-500:]})
        if args.labels:
            labels = desired_labels(decision)
            applied.extend(reconcile_labels(str(repo), int(pr), labels, root))
        if args.allow_merge and state == "READY_TO_MERGE" and "MERGE_PR" in decision.get("actions", []):
            merge_result = perform_policy_merge(root, args.policy, str(repo), int(pr), decision)
            applied.append(merge_result)
            if int(merge_result.get("exit_code") or 0) != 0:
                raise SystemExit(int(merge_result.get("exit_code") or 1))

    report = {"status": "PASS", "decision": decision, "applied": applied, "apply": args.apply, "allow_merge": args.allow_merge}
    out = root / args.report
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
