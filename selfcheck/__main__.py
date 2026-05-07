from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

KINDS = {
    "invariant": ("invariants", "schemas/invariant.schema.json"),
    "capability": ("capabilities", "schemas/capability.schema.json"),
    "project": ("projects", "schemas/project.schema.json"),
    "feature": ("features", "schemas/feature.schema.json"),
    "verifier": ("verifiers", "schemas/verifier.schema.json"),
    "loop": ("loops", "schemas/loop.schema.json"),
    "event": ("events", "schemas/event-route.schema.json"),
    "repair_policy": ("repair-policies", "schemas/repair-policy.schema.json"),
    "pr_autonomy_policy": ("pr-autonomy-policies", "schemas/pr-autonomy-policy.schema.json"),
    "role_model_routing": ("role-model-routing", "schemas/role-model-routing.schema.json"),
}

SAFE_EXECUTABLE_KINDS = {"static", "unit", "evidence", "api", "browser"}


@dataclass
class Issue:
    level: str
    path: str
    message: str


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def iter_yaml(root: Path, folder: str):
    d = root / folder
    if not d.exists():
        return
    for p in sorted(d.glob("*.yaml")):
        yield p


def load_schema(root: Path, rel: str) -> dict[str, Any]:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def load_index(root: Path, kind: str) -> dict[str, dict[str, Any]]:
    folder, _ = KINDS[kind]
    out = {}
    for p in iter_yaml(root, folder) or []:
        data = load_yaml(p)
        out[data["id"]] = data | {"__path": str(p)}
    return out


def validate(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    indexes: dict[str, dict[str, dict[str, Any]]] = {}

    for kind, (folder, schema_rel) in KINDS.items():
        schema = load_schema(root, schema_rel)
        index = {}
        for p in iter_yaml(root, folder) or []:
            try:
                data = load_yaml(p)
                jsonschema.validate(instance=data, schema=schema)
                expected = p.stem
                if data.get("id") != expected:
                    issues.append(Issue("WARN", str(p), f"id '{data.get('id')}' does not match filename '{expected}'"))
                if data["id"] in index:
                    issues.append(Issue("ERROR", str(p), f"duplicate {kind} id {data['id']}"))
                index[data["id"]] = data | {"__path": str(p)}
            except Exception as e:
                issues.append(Issue("ERROR", str(p), str(e)))
        indexes[kind] = index

    verifier_ids = set(indexes.get("verifier", {}))
    capability_ids = set(indexes.get("capability", {}))
    project_ids = set(indexes.get("project", {}))
    repair_policy_ids = set(indexes.get("repair_policy", {}))

    for cid, cap in indexes.get("capability", {}).items():
        for vid in cap.get("verifiers", []):
            if vid not in verifier_ids:
                issues.append(Issue("ERROR", cap["__path"], f"capability {cid} references missing verifier {vid}"))

    for fid, feat in indexes.get("feature", {}).items():
        if feat["project"] not in project_ids:
            issues.append(Issue("ERROR", feat["__path"], f"feature {fid} references missing project {feat['project']}"))
        for cid in feat.get("depends_on", []):
            if cid not in capability_ids:
                issues.append(Issue("ERROR", feat["__path"], f"feature {fid} references missing capability {cid}"))
        for group, vids in feat.get("must_pass", {}).items():
            for vid in vids:
                if vid not in verifier_ids:
                    issues.append(Issue("ERROR", feat["__path"], f"feature {fid} must_pass.{group} references missing verifier {vid}"))
        for alias, sid in feat.get("target_services", {}).items():
            project = indexes.get("project", {}).get(feat["project"], {})
            if sid not in project.get("services", {}):
                issues.append(Issue("ERROR", feat["__path"], f"feature {fid} target_services.{alias} references missing service {sid}"))
        if feat.get("repair_policy") and feat["repair_policy"] not in repair_policy_ids:
            issues.append(Issue("ERROR", feat["__path"], f"feature {fid} references missing repair_policy {feat['repair_policy']}"))
        if not feat.get("human_required"):
            issues.append(Issue("ERROR", feat["__path"], f"feature {fid} has no human_required boundaries"))
        if "final-verification" not in feat.get("reviewer_gates", []):
            issues.append(Issue("WARN", feat["__path"], f"feature {fid} lacks final-verification reviewer gate"))

    feature_ids = set(indexes.get("feature", {}))
    feature_groups = {fid: set(feat.get("must_pass", {})) for fid, feat in indexes.get("feature", {}).items()}
    for eid, route in indexes.get("event", {}).items():
        fid = route["feature"]
        if fid not in feature_ids:
            issues.append(Issue("ERROR", route["__path"], f"event route {eid} references missing feature {fid}"))
            continue
        missing_groups = set(route.get("groups", [])) - feature_groups.get(fid, set())
        if missing_groups:
            issues.append(Issue("ERROR", route["__path"], f"event route {eid} references missing feature groups: {', '.join(sorted(missing_groups))}"))

    return issues


def feature_plan(root: Path, feature_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    features = load_index(root, "feature")
    verifiers = load_index(root, "verifier")
    if feature_id not in features:
        raise SystemExit(f"Unknown feature: {feature_id}")
    feature = features[feature_id]
    ordered = []
    for group, ids in feature.get("must_pass", {}).items():
        for vid in ids:
            v = verifiers.get(vid)
            if v:
                ordered.append({"group": group, **v})
    return feature, ordered


def audit(root: Path, feature_id: str | None = None, strict_missing: bool = False) -> list[Issue]:
    issues = validate(root)
    features = load_index(root, "feature")
    selected = {feature_id: features[feature_id]} if feature_id else features
    for fid, feat in selected.items():
        for rel in feat.get("evidence_required", []):
            p = Path(rel)
            if not p.is_absolute():
                p = root / p
            try:
                exists = p.exists()
            except OSError as exc:
                issues.append(
                    Issue(
                        "ERROR" if strict_missing else "WARN",
                        str(p),
                        f"cannot access required evidence for feature {fid}: {exc}",
                    )
                )
                continue
            if not exists:
                issues.append(Issue("ERROR" if strict_missing else "WARN", str(p), f"missing required evidence for feature {fid}"))
    return issues


def print_issues(issues: list[Issue]) -> int:
    if not issues:
        print("PASS: no issues")
        return 0
    for i in issues:
        print(f"{i.level}: {i.path}: {i.message}")
    return 1 if any(i.level == "ERROR" for i in issues) else 0


def pick_service(feature: dict[str, Any], project: dict[str, Any], verifier: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    services = project.get("services", {})
    targets = feature.get("target_services", {})
    vid = verifier["id"]
    if vid.startswith("frontend-") and targets.get("frontend"):
        sid = targets["frontend"]
        return sid, services[sid]
    if vid.startswith("backend-") and targets.get("backend"):
        sid = targets["backend"]
        return sid, services[sid]
    for sid, svc in services.items():
        kind = str(svc.get("kind", ""))
        if vid.startswith("frontend-") and "frontend" in kind:
            return sid, svc
        if vid.startswith("backend-") and "backend" in kind:
            return sid, svc
    return None, {}


def lookup(ctx: dict[str, Any], expr: str) -> Any:
    cur: Any = ctx
    for part in expr.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(expr)
    return cur


def render_template(template: str, ctx: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        return str(lookup(ctx, match.group(1)))
    return re.sub(r"\{([a-zA-Z0-9_.-]+)\}", repl, template)


def render_command(root: Path, feature: dict[str, Any], verifier: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    projects = load_index(root, "project")
    project = projects[feature["project"]]
    service_id, service = pick_service(feature, project, verifier)
    ctx = {"project": project, "service": service, "feature": feature, "service_id": service_id or ""}
    command = render_template(verifier.get("command", ""), ctx)
    return command, {"project": project["id"], "service": service_id, "verifier": verifier["id"]}




def resolve_service_command(root: Path, feature: dict[str, Any], verifier: dict[str, Any]) -> tuple[Path | None, list[str] | None, str, dict[str, Any]]:
    projects = load_index(root, "project")
    project = projects[feature["project"]]
    service_id, service = pick_service(feature, project, verifier)
    rendered, resolved = render_command(root, feature, verifier)
    command_key = verifier.get("service_command")
    if not command_key:
        return None, None, rendered, resolved
    if not service_id or not service:
        raise ValueError(f"verifier {verifier['id']} requires a service but none resolved")
    project_root = Path(project["root"]).resolve()
    service_path = Path(service.get("path", ""))
    if service_path.is_absolute() or ".." in service_path.parts:
        raise ValueError(f"unsafe service path for {service_id}: {service_path}")
    cwd = (project_root / service_path).resolve()
    if project_root not in [cwd, *cwd.parents]:
        raise ValueError(f"resolved cwd escapes project root: {cwd}")
    if not cwd.exists():
        raise ValueError(f"resolved cwd does not exist: {cwd}")
    command_string = service.get("commands", {}).get(command_key)
    if not command_string:
        raise ValueError(f"service {service_id} has no command key {command_key}")
    if re.search(r"[;&|`$<>]", command_string):
        raise ValueError(f"service command {service_id}.{command_key} contains shell metacharacters")
    argv = shlex.split(command_string)
    if not argv:
        raise ValueError(f"service command {service_id}.{command_key} is empty")
    return cwd, argv, rendered, resolved

def write_report(root: Path, feature_id: str, verifier_id: str, report: dict[str, Any]) -> Path:
    d = root / "reports" / feature_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{verifier_id}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def resolve_harness_command(root: Path, command: str) -> tuple[list[str], Path]:
    argv = shlex.split(command)
    if not argv:
        raise ValueError("harness command is empty")
    script = Path(argv[0])
    if script.is_absolute() or ".." in script.parts:
        raise ValueError(f"unsafe harness path: {script}")
    script_path = (root / script).resolve()
    scripts_root = (root / "scripts").resolve()
    if scripts_root not in [script_path, *script_path.parents]:
        raise ValueError(f"harness escapes scripts directory: {script_path}")
    if not script_path.exists():
        raise ValueError(f"harness not found: {script_path}")
    return [str(script_path), *argv[1:]], root


def run_verifier(root: Path, feature: dict[str, Any], verifier: dict[str, Any], timeout: int) -> dict[str, Any]:
    cwd, argv, command, resolved = resolve_service_command(root, feature, verifier)
    started = time.time()
    report: dict[str, Any] = {
        "feature": feature["id"],
        "verifier": verifier["id"],
        "kind": verifier["kind"],
        "group": verifier.get("group"),
        "resolved": resolved,
        "command": command,
        "started_at_epoch": started,
    }
    if verifier["kind"] not in SAFE_EXECUTABLE_KINDS:
        report.update({"status": "SKIPPED", "reason": f"kind {verifier['kind']} requires project-specific harness"})
        return report
    if not command:
        report.update({"status": "SKIPPED", "reason": "no command"})
        return report
    try:
        if argv is not None and cwd is not None:
            proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        else:
            if verifier["kind"] == "evidence" and command.startswith("python3 -m selfcheck audit "):
                proc = subprocess.run(shlex.split(command), cwd=root, capture_output=True, text=True, timeout=timeout)
            elif verifier["kind"] in {"static", "unit", "api", "browser"}:
                harness_argv, harness_cwd = resolve_harness_command(root, command)
                proc = subprocess.run(harness_argv, cwd=harness_cwd, capture_output=True, text=True, timeout=timeout)
            else:
                raise ValueError("generic shell command execution is disabled; use service_command or a dedicated harness")
        report.update({
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "exit_code": proc.returncode,
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        })
    except subprocess.TimeoutExpired as e:
        report.update({
            "status": "FAIL",
            "exit_code": None,
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": (e.stdout or "")[-4000:] if isinstance(e.stdout, str) else "",
            "stderr_tail": (e.stderr or "")[-4000:] if isinstance(e.stderr, str) else "",
            "error": f"timeout after {timeout}s",
        })
    except Exception as e:
        report.update({
            "status": "FAIL",
            "exit_code": None,
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": "",
            "stderr_tail": "",
            "error": str(e),
        })
    return report


def load_payload(payload: str | None, payload_file: str | None) -> dict[str, Any]:
    if payload_file:
        return json.loads(Path(payload_file).read_text(encoding="utf-8"))
    if payload:
        return json.loads(payload)
    return {}


def match_event_routes(root: Path, event_name: str) -> list[dict[str, Any]]:
    routes = load_index(root, "event")
    matched = []
    for route in routes.values():
        pattern = route["event"]
        if pattern == event_name or pattern == "*" or (pattern.endswith(".*") and event_name.startswith(pattern[:-1])):
            matched.append(route)
    return matched


def write_event_report(root: Path, event_name: str, report: dict[str, Any], update_latest: bool = True) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", event_name).strip("-") or "event"
    d = root / "reports" / "events"
    d.mkdir(parents=True, exist_ok=True)
    content = json.dumps(report, ensure_ascii=False, indent=2)
    p = d / f"{safe}-{int(time.time())}.json"
    p.write_text(content, encoding="utf-8")
    if update_latest:
        latest = d / f"{safe}-latest.json"
        latest.write_text(content, encoding="utf-8")
    return p


def run_feature_groups(root: Path, feature_id: str, groups: list[str], timeout: int, allow_skipped: bool = False) -> list[dict[str, Any]]:
    feature, verifiers = feature_plan(root, feature_id)
    selected_groups = set(groups)
    available_groups = {v["group"] for v in verifiers}
    if not selected_groups <= available_groups:
        raise ValueError(f"unknown verifier group(s): {', '.join(sorted(selected_groups - available_groups))}")
    results = []
    for v in verifiers:
        if v["group"] not in selected_groups:
            continue
        report = run_verifier(root, feature, v, timeout)
        path = write_report(root, feature["id"], v["id"], report)
        report["report_path"] = str(path)
        report["ok"] = report["status"] != "FAIL" and (report["status"] != "SKIPPED" or allow_skipped)
        results.append(report)
    return results


def loop_dir(root: Path, feature_id: str) -> Path:
    d = root / "reports" / "loops" / feature_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_loop_state(root: Path, feature_id: str) -> dict[str, Any]:
    p = loop_dir(root, feature_id) / "state.json"
    if not p.exists():
        return {"attempts": 0, "failure_counts": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"attempts": 0, "failure_counts": {}}


def save_loop_state(root: Path, feature_id: str, state: dict[str, Any]) -> None:
    (loop_dir(root, feature_id) / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def reset_loop_state(root: Path, feature_id: str) -> None:
    p = loop_dir(root, feature_id) / "state.json"
    if p.exists():
        p.unlink()


def load_repair_policy(root: Path, feature: dict[str, Any]) -> dict[str, Any]:
    policies = load_index(root, "repair_policy")
    pid = feature.get("repair_policy") or "default-repair-policy"
    if pid not in policies:
        raise ValueError(f"missing repair policy: {pid}")
    return policies[pid]


def failure_signature(failures: list[dict[str, Any]]) -> str:
    parts = []
    for f in failures:
        parts.append(f"{f.get('group')}:{f.get('verifier')}:{f.get('status')}:{f.get('exit_code')}")
    return "|".join(sorted(parts)) or "no-failure"


def classify_failures(results: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    owners = policy.get("owners", {})
    out = []
    for r in results:
        if r.get("ok"):
            continue
        group = r.get("group") or r.get("kind") or "unknown"
        status = r.get("status")
        text = "\n".join(str(r.get(k, "")) for k in ["error", "stderr_tail", "stdout_tail"])
        reason = "verifier_failed"
        owner_key = group
        if status == "SKIPPED":
            reason = "verifier_skipped"
            owner_key = "evidence"
        if "missing required evidence" in text or group == "evidence":
            reason = "missing_evidence"
            owner_key = "evidence"
        if any(tok in text.lower() for tok in ["permission", "unauthorized", "forbidden", "secret", "token"]):
            reason = "missing_secret_or_permission"
            owner_key = "human-boundary"
        if any(tok in text.lower() for tok in ["connection refused", "timed out", "timeout", "service unavailable"]):
            reason = "runtime_unavailable"
            owner_key = group
        out.append({
            "group": group,
            "verifier": r.get("verifier"),
            "status": status,
            "exit_code": r.get("exit_code"),
            "report_path": r.get("report_path"),
            "reason": reason,
            "owner": owners.get(owner_key, owners.get(group, "developer")),
        })
    return out


def dispatch_dir(root: Path, feature_id: str) -> Path:
    d = root / ".hermes" / "dispatch" / feature_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_dispatch_artifacts(root: Path, feature: dict[str, Any], policy: dict[str, Any], failures: list[dict[str, Any]], attempt: int, terminal: str) -> list[str]:
    created = []
    by_owner: dict[str, list[dict[str, Any]]] = {}
    for f in failures:
        by_owner.setdefault(f["owner"], []).append(f)
    ts = int(time.time())
    for owner, items in sorted(by_owner.items()):
        md = dispatch_dir(root, feature["id"]) / f"{ts}-attempt-{attempt}-{owner}.md"
        lines = [
            f"# Repair Assignment: {feature['id']}",
            "",
            f"Owner: {owner}",
            f"Attempt: {attempt}",
            f"Loop status: {terminal}",
            "",
            "## Failed checks",
        ]
        for item in items:
            lines += [
                f"- verifier: `{item['verifier']}`",
                f"  group: `{item['group']}`",
                f"  status: `{item['status']}`",
                f"  reason: `{item['reason']}`",
                f"  evidence: `{item.get('report_path')}`",
            ]
        lines += [
            "",
            "## Required behavior",
            "- Investigate root cause before patching.",
            "- Do not change acceptance criteria or remove failing verifiers.",
            "- Implement fixes only in the assigned owner role; SelfCheck remains verifier/control-plane.",
            "- After fix, rerun:",
            f"  `python3 -m selfcheck loop --root . --feature {feature['id']} --groups <affected-groups> --timeout 300`",
            "",
            "## Review after fix",
        ]
        for reviewer in policy.get("review_after_fix", []):
            lines.append(f"- {reviewer}")
        md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        created.append(str(md))
    return created


def write_loop_report(root: Path, feature_id: str, report: dict[str, Any]) -> Path:
    d = loop_dir(root, feature_id)
    content = json.dumps(report, ensure_ascii=False, indent=2)
    p = d / f"loop-{int(time.time())}.json"
    p.write_text(content, encoding="utf-8")
    (d / "latest.json").write_text(content, encoding="utf-8")
    return p


def cmd_loop(args):
    root = Path(args.root)
    validation_issues = validate(root)
    if any(i.level == "ERROR" for i in validation_issues):
        raise SystemExit(print_issues(validation_issues))
    feature, planned_verifiers = feature_plan(root, args.feature)
    policy = load_repair_policy(root, feature)
    all_groups = set(feature.get("must_pass", {}).keys())
    groups = [g.strip() for g in (args.groups or ",".join(sorted(all_groups))).split(",") if g.strip()]
    if not groups:
        raise SystemExit("--groups resolved to no verifier groups; refusing empty PASS")
    selected_groups = set(groups)
    if not selected_groups <= all_groups:
        raise SystemExit(f"Unknown verifier group(s): {', '.join(sorted(selected_groups - all_groups))}")
    selected_verifiers = [v for v in planned_verifiers if v["group"] in selected_groups]
    if not selected_verifiers:
        raise SystemExit("selected verifier groups contain no verifiers; refusing empty PASS")
    full_selection = selected_groups == all_groups
    state = load_loop_state(root, feature["id"])
    if args.reset_state:
        state = {"attempts": 0, "failure_counts": {}}
    state["attempts"] = int(state.get("attempts", 0)) + 1
    started = time.time()
    results = run_feature_groups(root, feature["id"], groups, args.timeout, args.allow_skipped)
    failures = classify_failures(results, policy)
    if args.inject_failure:
        for injected in args.inject_failure:
            group, _, verifier = injected.partition(":")
            failures.append({"group": group or "static", "verifier": verifier or "injected-failure", "status": "FAIL", "exit_code": 1, "report_path": None, "reason": "injected_test_failure", "owner": policy.get("owners", {}).get(group or "static", "developer")})
    audit_issues: list[Issue] = []
    if args.strict_audit:
        audit_issues = audit(root, feature["id"], strict_missing=True)
        for issue in audit_issues:
            if issue.level == "ERROR":
                failures.append({"group": "evidence", "verifier": "strict-audit", "status": "FAIL", "exit_code": None, "report_path": issue.path, "reason": "missing_evidence", "owner": policy.get("owners", {}).get("evidence", "orchestrator")})
    sig = failure_signature(failures)
    failure_counts = state.setdefault("failure_counts", {})
    if failures:
        failure_counts[sig] = int(failure_counts.get(sig, 0)) + 1
    terminal = "PASS" if not failures else "NEEDS_REPAIR"
    if not failures and (not full_selection or not args.strict_audit):
        terminal = "PASS_WITH_NOTES"
    escalation_reasons = []
    if failures:
        if int(state["attempts"]) >= int(policy["max_attempts"]):
            escalation_reasons.append("attempts_exhausted")
        if int(failure_counts.get(sig, 0)) >= int(policy["same_failure_limit"]):
            escalation_reasons.append("repeated_same_failure")
        if any(f["owner"] == "human" for f in failures):
            escalation_reasons.append("human_boundary_required")
        if escalation_reasons:
            terminal = "BLOCKED"
            escalation_owner = "human" if "human_boundary_required" in escalation_reasons else "orchestrator"
            for f in failures:
                f["owner"] = escalation_owner
                f["reason"] = f"escalation:{','.join(escalation_reasons)}"
    dispatches = [] if terminal in {"PASS", "PASS_WITH_NOTES"} else write_dispatch_artifacts(root, feature, policy, failures, int(state["attempts"]), terminal)
    if terminal == "PASS":
        reset_loop_state(root, feature["id"])
    elif terminal == "PASS_WITH_NOTES":
        save_loop_state(root, feature["id"], state)
    else:
        save_loop_state(root, feature["id"], state)
    report = {
        "feature": feature["id"],
        "policy": policy["id"],
        "status": terminal,
        "attempt": int(state["attempts"]),
        "groups": groups,
        "duration_seconds": round(time.time() - started, 3),
        "failures": failures,
        "escalation_reasons": escalation_reasons,
        "dispatches": dispatches,
        "verifiers": [{"id": r.get("verifier"), "group": r.get("group"), "status": r.get("status"), "ok": r.get("ok"), "report_path": r.get("report_path")} for r in results],
        "audit": [{"level": i.level, "path": i.path, "message": i.message} for i in audit_issues],
    }
    p = write_loop_report(root, feature["id"], report)
    print(f"{terminal}: {feature['id']} -> {p}")
    for d in dispatches:
        print(f"DISPATCH: {d}")
    if terminal in {"PASS", "PASS_WITH_NOTES"}:
        return
    if terminal == "BLOCKED":
        raise SystemExit(3)
    raise SystemExit(2)



def backtick_value(text: str, fallback: str) -> str:
    parts = text.split("`")
    return parts[1] if len(parts) >= 3 else fallback.strip()


def parse_dispatch_artifact(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    def grab(prefix: str) -> str | None:
        for line in text.splitlines():
            if line.startswith(prefix):
                return line[len(prefix):].strip()
        return None
    owner = grab("Owner:") or "unknown"
    attempt_s = grab("Attempt:") or "0"
    status = grab("Loop status:") or "UNKNOWN"
    title = next((line.removeprefix("# Repair Assignment:").strip() for line in text.splitlines() if line.startswith("# Repair Assignment:")), path.parent.name)
    failed = []
    cur: dict[str, Any] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- verifier:"):
            if cur:
                failed.append(cur)
            cur = {"verifier": backtick_value(stripped, stripped.removeprefix("- verifier:"))}
        elif cur is not None and stripped.startswith("group:"):
            cur["group"] = backtick_value(stripped, stripped.removeprefix("group:"))
        elif cur is not None and stripped.startswith("status:"):
            cur["status"] = backtick_value(stripped, stripped.removeprefix("status:"))
        elif cur is not None and stripped.startswith("reason:"):
            cur["reason"] = backtick_value(stripped, stripped.removeprefix("reason:"))
        elif cur is not None and stripped.startswith("evidence:"):
            cur["evidence"] = backtick_value(stripped, stripped.removeprefix("evidence:"))
    if cur:
        failed.append(cur)
    meta_path = path.with_suffix(path.suffix + ".json")
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as e:
            meta = {"state": "CORRUPT", "error": str(e)}
    return {
        "path": str(path),
        "feature": title,
        "owner": owner,
        "attempt": int(attempt_s) if str(attempt_s).isdigit() else attempt_s,
        "loop_status": status,
        "failed_checks": failed,
        "state": meta.get("state", "OPEN"),
        "claimed_by": meta.get("claimed_by"),
        "completed_by": meta.get("completed_by"),
        "meta_path": str(meta_path),
    }


def iter_dispatch_artifacts(root: Path, feature: str | None = None, owner: str | None = None, include_closed: bool = False) -> list[dict[str, Any]]:
    base = root / ".hermes" / "dispatch"
    if not base.exists():
        return []
    paths = sorted((base / feature).glob("*.md") if feature else base.glob("*/*.md"))
    out = []
    for path in paths:
        item = parse_dispatch_artifact(path)
        if owner and item["owner"] != owner:
            continue
        if not include_closed and item["state"] in {"COMPLETED", "CANCELLED"}:
            continue
        out.append(item)
    return out


def dispatch_prompt(item: dict[str, Any]) -> str:
    groups = sorted({str(f.get("group")) for f in item.get("failed_checks", []) if f.get("group")})
    checks = "\n".join(f"- {f.get('group')} / {f.get('verifier')}: {f.get('reason')} ({f.get('evidence')})" for f in item.get("failed_checks", [])) or "- no parsed checks"
    return f"""Role: {item['owner']}
Feature: {item['feature']}
Dispatch artifact: {item['path']}
Loop status: {item['loop_status']}
Attempt: {item['attempt']}

Task:
Investigate and fix the assigned SelfCheck failure in the correct role. Do not change acceptance criteria or remove failing verifiers. Preserve role separation: implementer fixes implementation; reviewer/QA only review/verify.

Failed checks:
{checks}

After the fix, rerun:
python3 -m selfcheck loop --root . --feature {item['feature']} --groups {','.join(groups) or '<affected-groups>'} --strict-audit --timeout 300

Return:
- files changed
- root cause
- fix summary
- verification commands and results
- remaining risks or BLOCKED reason
"""


def write_dispatch_meta(item: dict[str, Any], updates: dict[str, Any]) -> Path:
    meta_path = Path(item["meta_path"])
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    meta.update(updates)
    meta["updated_at_epoch"] = time.time()
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta_path



def safe_path_segment(value: Any, fallback: str = "unknown") -> str:
    text = str(value or fallback)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip(".-")
    return safe or fallback


def dispatch_runs_dir(root: Path, feature: str) -> Path:
    d = root / ".hermes" / "dispatch-runs" / safe_path_segment(feature, "feature")
    d.mkdir(parents=True, exist_ok=True)
    return d


def run_external_executor(root: Path, item: dict[str, Any], prompt_path: Path, executor_command: str | None, timeout: int) -> dict[str, Any]:
    if not executor_command:
        return {"status": "SKIPPED", "reason": "no executor command supplied"}
    argv = shlex.split(executor_command)
    if not argv:
        raise SystemExit("--executor-command resolved to empty argv")
    env = os.environ.copy()
    env.update({
        "SELFCHECK_ROOT": str(root),
        "SELFCHECK_DISPATCH_PATH": item["path"],
        "SELFCHECK_FEATURE": item["feature"],
        "SELFCHECK_OWNER": item["owner"],
        "SELFCHECK_PROMPT_FILE": str(prompt_path),
    })
    started = time.time()
    try:
        proc = subprocess.run(argv, cwd=root, env=env, text=True, capture_output=True, timeout=timeout)
        return {
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "argv": argv,
            "exit_code": proc.returncode,
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    except Exception as e:
        return {
            "status": "FAIL",
            "argv": argv,
            "exit_code": None,
            "duration_seconds": round(time.time() - started, 3),
            "error_type": type(e).__name__,
            "error": str(e),
        }


def consume_dispatch(root: Path, item: dict[str, Any], actor: str, executor_command: str | None, timeout: int, loop_timeout: int, force: bool = False, allow_no_executor: bool = False) -> dict[str, Any]:
    if not executor_command and not allow_no_executor:
        raise SystemExit("--executor-command is required for consume unless --allow-no-executor is set")
    run_id = f"{time.time_ns()}-{os.getpid()}-{safe_path_segment(item['owner'], 'owner')}-{safe_path_segment(Path(item['path']).stem, 'dispatch')}"
    run_dir = dispatch_runs_dir(root, item["feature"]) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt = dispatch_prompt(item)
    prompt_path = run_dir / "delegate_task_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    if item["state"] not in {"OPEN", "CLAIMED"} and not force:
        raise SystemExit(f"cannot consume dispatch in state {item['state']} without --force")
    claimed = parse_dispatch_artifact(Path(item["path"]))
    if claimed["state"] == "OPEN":
        write_dispatch_meta(claimed, {"state": "CLAIMED", "claimed_by": actor, "claimed_at_epoch": time.time(), "consume_run_id": run_id})
        claimed = parse_dispatch_artifact(Path(item["path"]))
    if claimed["state"] != "CLAIMED" and not force:
        raise SystemExit(f"cannot consume dispatch after refresh in state {claimed['state']} without --force")
    executor_result = run_external_executor(root, claimed, prompt_path, executor_command, timeout)
    if executor_result["status"] == "FAIL":
        report = {"status": "EXECUTOR_FAIL", "dispatch": claimed, "prompt_path": str(prompt_path), "executor": executor_result}
        (run_dir / "consume-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(4)
    groups = sorted({str(f.get("group")) for f in claimed.get("failed_checks", []) if f.get("group")})
    if not groups:
        raise SystemExit("dispatch contains no affected groups; refusing unverifiable consume")
    # Rerun through SelfCheck itself; this is the verification boundary after owner/executor work.
    loop_args = argparse.Namespace(root=str(root), feature=claimed["feature"], groups=",".join(groups), timeout=loop_timeout, allow_skipped=False, strict_audit=True, reset_state=False, inject_failure=None)
    loop_status = "PASS"
    loop_exit = 0
    try:
        cmd_loop(loop_args)
    except SystemExit as e:
        loop_exit = int(e.code) if isinstance(e.code, int) else 1
        loop_status = "FAIL"
    latest = root / "reports" / "loops" / claimed["feature"] / "latest.json"
    verified_status = None
    if latest.exists():
        verified_status = json.loads(latest.read_text(encoding="utf-8")).get("status")
    pass_like = loop_exit == 0 and verified_status in {"PASS", "PASS_WITH_NOTES"}
    if pass_like:
        write_dispatch_meta(parse_dispatch_artifact(Path(claimed["path"])), {"state": "COMPLETED", "completed_by": actor, "completed_at_epoch": time.time(), "result": "consume runner verified fix", "verified_report": str(latest.relative_to(root)), "verified_status": verified_status, "consume_run_id": run_id})
    report = {
        "status": "COMPLETED" if pass_like else "VERIFY_FAIL",
        "dispatch": parse_dispatch_artifact(Path(claimed["path"])),
        "prompt_path": str(prompt_path),
        "executor": executor_result,
        "rerun_groups": groups,
        "loop_exit": loop_exit,
        "verified_report": str(latest),
        "verified_status": verified_status,
    }
    report_path = run_dir / "consume-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not pass_like:
        print(f"VERIFY_FAIL: {claimed['path']} -> {report_path}")
        raise SystemExit(5)
    print(f"CONSUMED: {claimed['path']} -> {report_path}")
    return report


def cmd_dispatch(args):
    root = Path(args.root)
    items = iter_dispatch_artifacts(root, args.feature, args.owner, include_closed=args.include_closed)
    if args.dispatch_action == "list":
        for item in items:
            print(f"{item['state']} owner={item['owner']} feature={item['feature']} attempt={item['attempt']} path={item['path']}")
        return
    if args.dispatch_action == "plan":
        if not items:
            print("NO_DISPATCH")
            return
        selected = items[0]
        print(json.dumps({"dispatch": selected, "delegate_task_prompt": dispatch_prompt(selected)}, ensure_ascii=False, indent=2))
        return
    if args.dispatch_action == "consume":
        if args.path:
            path = Path(args.path)
            if not path.is_absolute():
                path = root / path
            selected = parse_dispatch_artifact(path)
        else:
            if not items:
                print("NO_DISPATCH")
                return
            selected = items[0]
        consume_dispatch(root, selected, args.actor or "orchestrator", args.executor_command, args.executor_timeout, args.loop_timeout, args.force, args.allow_no_executor)
        return
    if not args.path:
        raise SystemExit("--path is required for claim/complete/cancel")
    path = Path(args.path)
    if not path.is_absolute():
        path = root / path
    item = parse_dispatch_artifact(path)
    if args.dispatch_action == "claim":
        if item["state"] in {"COMPLETED", "CANCELLED", "CORRUPT"} and not args.force:
            raise SystemExit(f"cannot claim dispatch in state {item['state']} without --force")
        p = write_dispatch_meta(item, {"state": "CLAIMED", "claimed_by": args.actor or item["owner"], "claimed_at_epoch": time.time()})
        print(f"CLAIMED: {item['path']} -> {p}")
        return
    if args.dispatch_action == "complete":
        if item["state"] != "CLAIMED" and not args.force:
            raise SystemExit(f"cannot complete dispatch in state {item['state']} without --force")
        if not args.result:
            raise SystemExit("--result is required for complete")
        if not args.verified_report and not args.force:
            raise SystemExit("--verified-report is required for complete")
        verified = None
        if args.verified_report:
            vp = Path(args.verified_report)
            if not vp.is_absolute():
                vp = root / vp
            verified = json.loads(vp.read_text(encoding="utf-8"))
            if verified.get("status") not in {"PASS", "PASS_WITH_NOTES"} and not args.force:
                raise SystemExit(f"verified report status is not pass-like: {verified.get('status')}")
        p = write_dispatch_meta(item, {"state": "COMPLETED", "completed_by": args.actor or item["owner"], "completed_at_epoch": time.time(), "result": args.result, "verified_report": args.verified_report, "verified_status": verified.get("status") if isinstance(verified, dict) else None})
        print(f"COMPLETED: {item['path']} -> {p}")
        return
    if args.dispatch_action == "cancel":
        p = write_dispatch_meta(item, {"state": "CANCELLED", "completed_by": args.actor or "orchestrator", "completed_at_epoch": time.time(), "result": args.result or "cancelled"})
        print(f"CANCELLED: {item['path']} -> {p}")
        return
    raise SystemExit(f"unknown dispatch action: {args.dispatch_action}")


def event_state_path(root: Path) -> Path:
    d = root / "reports" / "events"
    d.mkdir(parents=True, exist_ok=True)
    return d / ".state.json"


def load_event_state(root: Path) -> dict[str, Any]:
    p = event_state_path(root)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_event_state(root: Path, state: dict[str, Any]) -> None:
    event_state_path(root).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_trigger(args):
    root = Path(args.root)
    issues = validate(root)
    if any(i.level == "ERROR" for i in issues):
        raise SystemExit(print_issues(issues))
    payload = load_payload(args.payload, args.payload_file)
    source = args.source or str(payload.get("source") or "local")
    routes = match_event_routes(root, args.event)
    if args.route:
        routes = [r for r in routes if r["id"] == args.route]
    if not routes:
        report = {"event": args.event, "source": source, "status": "NO_ROUTE", "payload_keys": sorted(payload.keys())}
        p = write_event_report(root, args.event, report, update_latest=False)
        print(f"NO_ROUTE: {args.event} -> {p}")
        raise SystemExit(2)
    failures = 0
    skipped_only = True
    now = time.time()
    state = load_event_state(root)
    event_report = {"event": args.event, "source": source, "status": "DRY_RUN" if args.dry_run else "PASS", "routes": [], "payload_keys": sorted(payload.keys())}
    for route in routes:
        route_report = {"route": route["id"], "feature": route["feature"], "groups": route["groups"], "mode": route["mode"]}
        if route["id"] == "github-pr-autonomy":
            try:
                from selfcheck.pr_autonomy import dispatch_payload
                route_report["pr_autonomy_decision"] = dispatch_payload(root, "github-pr-autonomy-v-workspace", payload)
            except Exception as exc:
                route_report["pr_autonomy_decision"] = {"state": "BLOCKED", "terminal": True, "reason": f"dispatcher error: {exc}"}
        allowed_sources = set(route.get("allowed_sources", []))
        if allowed_sources and source not in allowed_sources:
            route_report.update({"status": "REJECTED", "reason": f"source {source} is not allowed"})
            failures += 1
            event_report["routes"].append(route_report)
            print(f"REJECTED: route={route['id']} source={source}")
            continue
        state_key = f"{route['id']}::{args.event}"
        debounce = int(route.get("debounce_seconds", 0) or 0)
        last = float(state.get(state_key, 0) or 0)
        if debounce and not args.dry_run and now - last < debounce:
            route_report.update({"status": "DEBOUNCED", "seconds_since_last": round(now - last, 3), "debounce_seconds": debounce})
            event_report["routes"].append(route_report)
            print(f"DEBOUNCED: route={route['id']} event={args.event}")
            continue
        if args.dry_run:
            route_report["status"] = "DRY_RUN"
            print(f"DRY-RUN route={route['id']} feature={route['feature']} groups={','.join(route['groups'])}")
        else:
            skipped_only = False
            results = run_feature_groups(root, route["feature"], route["groups"], args.timeout, args.allow_skipped)
            route_report["verifiers"] = [{"id": r["verifier"], "status": r["status"], "report_path": r.get("report_path")} for r in results]
            route_ok = all(r["ok"] for r in results)
            if route.get("strict_audit"):
                audit_issues = audit(root, route["feature"], strict_missing=True)
                route_report["audit"] = [{"level": i.level, "path": i.path, "message": i.message} for i in audit_issues]
                route_ok = route_ok and not any(i.level == "ERROR" for i in audit_issues)
            route_report["status"] = "PASS" if route_ok else "FAIL"
            if route_ok:
                state[state_key] = now
            else:
                failures += 1
            print(f"{route_report['status']}: route={route['id']} feature={route['feature']}")
        event_report["routes"].append(route_report)
    if failures:
        event_report["status"] = "FAIL"
    elif not args.dry_run and skipped_only:
        event_report["status"] = "NOOP"
    if not args.dry_run:
        save_event_state(root, state)
    p = write_event_report(root, args.event, event_report, update_latest=(not args.dry_run and (failures > 0 or not skipped_only)))
    print(f"EVENT_REPORT: {p}")
    if failures:
        raise SystemExit(1)

def cmd_validate(args):
    raise SystemExit(print_issues(validate(Path(args.root))))


def cmd_audit(args):
    raise SystemExit(print_issues(audit(Path(args.root), args.feature, args.strict_missing)))


def cmd_plan(args):
    root = Path(args.root)
    feature, verifiers = feature_plan(root, args.feature)
    print(f"Feature: {feature['id']} ({feature.get('level_target', 'n/a')})")
    print(f"Project: {feature['project']}")
    print("Capabilities: " + ", ".join(feature.get("depends_on", [])))
    print("Human-required boundaries:")
    for h in feature.get("human_required", []):
        print(f"- {h}")
    print("Verifier plan:")
    for v in verifiers:
        try:
            command, resolved = render_command(root, feature, v)
            svc = resolved.get("service") or "-"
        except Exception:
            command, svc = v.get("command", "<manual>"), "?"
        print(f"- [{v['group']}] {v['id']} ({v['kind']}, service={svc}): {command}")


def cmd_run(args):
    root = Path(args.root)
    validation_issues = validate(root)
    if any(i.level == "ERROR" for i in validation_issues):
        raise SystemExit(print_issues(validation_issues))
    feature, verifiers = feature_plan(root, args.feature)
    available_groups = {v["group"] for v in verifiers}
    selected_groups = set(args.groups.split(",")) if args.groups else None
    if selected_groups and not selected_groups <= available_groups:
        raise SystemExit(f"Unknown verifier group(s): {', '.join(sorted(selected_groups - available_groups))}")
    failures = 0
    for v in verifiers:
        if selected_groups and v["group"] not in selected_groups:
            continue
        command, _ = render_command(root, feature, v)
        if args.dry_run:
            print(f"DRY-RUN {v['id']}: {command}")
            continue
        report = run_verifier(root, feature, v, args.timeout)
        p = write_report(root, feature["id"], v["id"], report)
        print(f"{report['status']}: {v['id']} -> {p}")
        if report["status"] == "FAIL" or (report["status"] == "SKIPPED" and not args.allow_skipped):
            failures += 1
    if failures:
        raise SystemExit(1)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="selfcheck")
    sub = ap.add_subparsers(required=True)
    for name, fn in [("validate", cmd_validate), ("audit", cmd_audit), ("plan", cmd_plan), ("run", cmd_run), ("trigger", cmd_trigger), ("loop", cmd_loop), ("dispatch", cmd_dispatch)]:
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
        p.set_defaults(func=fn)
        if name in {"audit", "plan", "run", "loop"}:
            p.add_argument("--feature")
        if name == "trigger":
            p.add_argument("--event", required=True)
            p.add_argument("--route")
            p.add_argument("--payload")
            p.add_argument("--payload-file")
            p.add_argument("--source", help="event source, e.g. local, git-hook, ci-webhook, hermes-webhook, cron")
        if name == "dispatch":
            p.add_argument("dispatch_action", choices=["list", "plan", "claim", "complete", "cancel", "consume"])
            p.add_argument("--feature")
            p.add_argument("--owner")
            p.add_argument("--path")
            p.add_argument("--actor")
            p.add_argument("--result")
            p.add_argument("--include-closed", action="store_true")
            p.add_argument("--verified-report", help="loop report proving the fix before completing dispatch")
            p.add_argument("--force", action="store_true")
            p.add_argument("--executor-command", help="opt-in external owner executor command; run without shell with prompt/env vars")
            p.add_argument("--executor-timeout", type=int, default=600)
            p.add_argument("--loop-timeout", type=int, default=300)
            p.add_argument("--allow-no-executor", action="store_true", help="test-only: allow consume to verify without owner executor")
        if name == "audit":
            p.add_argument("--strict-missing", action="store_true")
        if name in {"run", "trigger"}:
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--timeout", type=int, default=300)
            p.add_argument("--allow-skipped", action="store_true")
        if name == "loop":
            p.add_argument("--groups", help="comma-separated must_pass groups to run")
            p.add_argument("--timeout", type=int, default=300)
            p.add_argument("--allow-skipped", action="store_true")
            p.add_argument("--strict-audit", action="store_true")
            p.add_argument("--reset-state", action="store_true")
            p.add_argument("--inject-failure", action="append", help="test-only injected failure as group:verifier")
        if name == "run":
            p.add_argument("--groups", help="comma-separated must_pass groups to run, e.g. static,evidence")
    args = ap.parse_args(argv)
    if getattr(args, "feature", None) is None and args.func in {cmd_plan, cmd_run, cmd_loop}:
        ap.error("--feature is required")
    args.func(args)


if __name__ == "__main__":
    main()
