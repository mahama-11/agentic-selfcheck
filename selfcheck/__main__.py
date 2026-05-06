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
}

SAFE_EXECUTABLE_KINDS = {"static", "unit", "evidence"}


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
        if not feat.get("human_required"):
            issues.append(Issue("ERROR", feat["__path"], f"feature {fid} has no human_required boundaries"))
        if "final-verification" not in feat.get("reviewer_gates", []):
            issues.append(Issue("WARN", feat["__path"], f"feature {fid} lacks final-verification reviewer gate"))

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
            if not p.exists():
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
            if verifier["kind"] != "evidence" or not command.startswith("python3 -m selfcheck audit "):
                raise ValueError("generic shell command execution is disabled; use service_command or a dedicated harness")
            proc = subprocess.run(shlex.split(command), cwd=root, capture_output=True, text=True, timeout=timeout)
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
    for name, fn in [("validate", cmd_validate), ("audit", cmd_audit), ("plan", cmd_plan), ("run", cmd_run)]:
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
        p.set_defaults(func=fn)
        if name in {"audit", "plan", "run"}:
            p.add_argument("--feature")
        if name == "audit":
            p.add_argument("--strict-missing", action="store_true")
        if name == "run":
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--groups", help="comma-separated must_pass groups to run, e.g. static,evidence")
            p.add_argument("--timeout", type=int, default=300)
            p.add_argument("--allow-skipped", action="store_true")
    args = ap.parse_args(argv)
    if getattr(args, "feature", None) is None and args.func in {cmd_plan, cmd_run}:
        ap.error("--feature is required")
    args.func(args)


if __name__ == "__main__":
    main()

