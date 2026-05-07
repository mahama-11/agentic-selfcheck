#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT_FOR_IMPORT = Path(__file__).resolve().parents[1]
if str(ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(ROOT_FOR_IMPORT))

from selfcheck.pr_autonomy import dispatch_payload


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def pr_payload(repo: str, *, action="opened", base="main", draft=False, changed=None, checks=None, repair_attempts=0, head_repo=None):
    return {
        "action": action,
        "repository": {"name": repo, "owner": {"login": "mahama-11"}},
        "pull_request": {"number": 42, "state": "open", "draft": draft, "base": {"ref": base}, "head": {"ref": "feature", "sha": "abc123", "repo": {"full_name": head_repo or f"mahama-11/{repo}"}}},
        "changed_files": changed if changed is not None else ["README.md"],
        "check_runs": checks or {},
        "repair_attempts": repair_attempts,
    }


def representative_events() -> dict[str, dict]:
    return {
        "unknown_repo": pr_payload("unknown", checks={}),
        "unknown_action": pr_payload("platform-backend", action="edited", changed=["README.md"], checks={"Go baseline checks": "success"}),
        "draft_pr": pr_payload("platform-backend", draft=True, changed=["README.md"], checks={"Go baseline checks": "success"}),
        "disallowed_base": pr_payload("platform-backend", base="develop", changed=["README.md"], checks={"Go baseline checks": "success"}),
        "missing_changed_files": pr_payload("platform-backend", changed=[], checks={"Go baseline checks": "success"}),
        "fork_pr_needs_human": pr_payload("platform-backend", head_repo="external/platform-backend", changed=["README.md"], checks={"Go baseline checks": "success"}),
        "pending_checks": pr_payload("platform-backend", changed=["README.md"], checks={"Go baseline checks": "in_progress"}),
        "missing_checks": pr_payload("platform-backend", changed=["README.md"], checks={}),
        "high_risk_workflow": pr_payload("platform-backend", changed=[".github/workflows/ci.yml"], checks={"Go baseline checks": "success"}),
        "large_diff": pr_payload("ecommerce-frontend", changed=[f"docs/file-{i}.md" for i in range(25)], checks={"Typecheck and build": "success"}),
        "medium_risk": pr_payload("platform-frontend", changed=["src/App.tsx"], checks={"Build": "success"}),
        "failed_checks_repair_scope_mismatch": pr_payload("ecommerce-frontend", action="synchronize", changed=["package.json"], checks={"Typecheck and build": "failure"}),
        "merge_enabled_clean_checks": pr_payload("ecommerce-frontend", action="ready_for_review", changed=["README.md"], checks={"Typecheck and build": "success"}),
    }


def repair_enabled_policy_report(root: Path, policy_id: str) -> dict:
    policy_path = root / "pr-autonomy-policies" / f"{policy_id}.yaml"
    policy = load_yaml(policy_path)
    policy["defaults"]["max_repair_attempts"] = 2
    target = next(r for r in policy["repositories"] if r["id"] == "mahama-11/ecommerce-backend")
    target["repair"]["enabled"] = True
    target["repair"]["max_attempts"] = 2
    target["repair"]["allowed_globs"] = ["README.md", "docs/*.md", "docs/**/*.md", "*.go", "**/*.go"]

    from selfcheck.pr_autonomy import compute_next_action, normalize_github_pr_event

    repairable_event = normalize_github_pr_event(pr_payload("ecommerce-backend", changed=["docs/repair.md"], checks={"Go tests": "failure"}))
    denied_event = normalize_github_pr_event(pr_payload("ecommerce-backend", changed=[".github/workflows/ci.yml"], checks={"Go tests": "failure"}))
    exhausted_event = normalize_github_pr_event(pr_payload("ecommerce-backend", changed=["docs/repair.md"], checks={"Go tests": "failure"}, repair_attempts=2))
    execution_disabled_policy = copy.deepcopy(policy)
    target_disabled = next(r for r in execution_disabled_policy["repositories"] if r["id"] == "mahama-11/ecommerce-backend")
    target_disabled["repair"]["enabled"] = True
    target_disabled["repair"]["execution_enabled"] = False
    target_disabled["repair"]["allowed_globs"] = ["README.md", "docs/*.md", "docs/**/*.md", "*.go", "**/*.go"]
    execution_disabled_event = normalize_github_pr_event(pr_payload("ecommerce-backend", changed=["docs/repair.md"], checks={"Go tests": "failure"}))
    return {
        "repairable": compute_next_action(repairable_event, policy, repair_attempts=0),
        "denied": compute_next_action(denied_event, policy, repair_attempts=0),
        "exhausted": compute_next_action(exhausted_event, policy, repair_attempts=2),
        "execution_disabled": compute_next_action(execution_disabled_event, execution_disabled_policy, repair_attempts=0),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--policy", default="github-pr-autonomy-v-workspace")
    parser.add_argument("--report", default="reports/github-pr-autonomy/github-pr-autonomy-policy-validate.json")
    args = parser.parse_args()

    root = Path(args.root)
    policy_path = root / "pr-autonomy-policies" / f"{args.policy}.yaml"
    schema_path = root / "schemas" / "pr-autonomy-policy.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    policy = load_yaml(policy_path)
    jsonschema.validate(policy, schema)

    results = {name: dispatch_payload(root, args.policy, payload) for name, payload in representative_events().items()}
    repair_results = repair_enabled_policy_report(root, args.policy)
    states = set(policy["states"])
    terminal_states = set(policy["terminal_states"])
    all_results = {**results, **{f"repair_{k}": v for k, v in repair_results.items()}}
    assertions = {
        "unknown_repo_ignored": results["unknown_repo"]["state"] == "IGNORED",
        "unknown_action_blocked": results["unknown_action"]["state"] == "BLOCKED",
        "draft_waits_for_author": results["draft_pr"]["state"] == "WAITING_FOR_AUTHOR" and results["draft_pr"]["terminal"] is False,
        "disallowed_base_blocked": results["disallowed_base"]["state"] == "BLOCKED",
        "missing_changed_files_needs_human": results["missing_changed_files"]["state"] == "NEEDS_HUMAN",
        "fork_pr_needs_human": results["fork_pr_needs_human"]["state"] == "NEEDS_HUMAN",
        "pending_checks_wait": results["pending_checks"]["state"] == "WAITING_FOR_CHECKS",
        "missing_checks_wait": results["missing_checks"]["state"] == "WAITING_FOR_CHECKS",
        "high_risk_needs_human": results["high_risk_workflow"]["state"] == "NEEDS_HUMAN",
        "large_diff_high_risk": results["large_diff"]["state"] == "NEEDS_HUMAN",
        "medium_risk_ready_for_human": results["medium_risk"]["state"] == "NEEDS_HUMAN" and results["medium_risk"]["risk"]["level"] == "medium",
        "failed_checks_scope_mismatch_needs_human": results["failed_checks_repair_scope_mismatch"]["state"] == "NEEDS_HUMAN",
        "clean_checks_ready_to_merge": results["merge_enabled_clean_checks"]["state"] == "READY_TO_MERGE" and "MERGE_PR" in results["merge_enabled_clean_checks"].get("actions", []),
        "repairable_path_dispatches": repair_results["repairable"]["state"] == "NEEDS_REPAIR",
        "repair_denied_needs_human": repair_results["denied"]["state"] == "NEEDS_HUMAN",
        "repair_exhausted_blocked": repair_results["exhausted"]["state"] == "BLOCKED",
        "repair_execution_disabled_blocks": repair_results["execution_disabled"]["state"] == "BLOCKED",
        "all_emitted_states_declared": all(result["state"] in states for result in all_results.values()),
        "terminal_states_declared": all((not result.get("terminal")) or result["state"] in terminal_states for result in all_results.values()),
        "merge_enabled_everywhere": policy["defaults"]["auto_merge"]["enabled"] is True and all(r["merge"]["auto_merge_enabled"] is True for r in policy["repositories"]),
        "live_merge_action_policy_gated": any(action == "MERGE_PR" for result in all_results.values() for action in result.get("actions", [])),
        "dry_run_disabled_for_live_rollout": all(result.get("dry_run") is False for result in all_results.values()),
    }
    ok = all(assertions.values())
    report = {"status": "PASS" if ok else "FAIL", "policy": args.policy, "assertions": assertions, "results": results, "repair_results": repair_results}
    report_path = root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
