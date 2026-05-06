from __future__ import annotations

import argparse
import json
import os
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


def audit(root: Path, feature_id: str | None = None) -> list[Issue]:
    issues = validate(root)
    features = load_index(root, "feature")
    selected = {feature_id: features[feature_id]} if feature_id else features
    for fid, feat in selected.items():
        for rel in feat.get("evidence_required", []):
            p = Path(rel)
            if not p.is_absolute():
                p = root / p
            if not p.exists():
                issues.append(Issue("WARN", str(p), f"missing required evidence for feature {fid}"))
    return issues


def print_issues(issues: list[Issue]) -> int:
    if not issues:
        print("PASS: no issues")
        return 0
    for i in issues:
        print(f"{i.level}: {i.path}: {i.message}")
    return 1 if any(i.level == "ERROR" for i in issues) else 0


def cmd_validate(args):
    raise SystemExit(print_issues(validate(Path(args.root))))


def cmd_audit(args):
    raise SystemExit(print_issues(audit(Path(args.root), args.feature)))


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
        print(f"- [{v['group']}] {v['id']} ({v['kind']}): {v.get('command', '<manual>')}")


def cmd_run(args):
    root = Path(args.root)
    _, verifiers = feature_plan(root, args.feature)
    if args.dry_run:
        for v in verifiers:
            print(f"DRY-RUN {v['id']}: {v.get('command', '<manual>')}")
        return
    raise SystemExit("Non-dry-run execution is intentionally not enabled in v0; wire project adapters first.")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="selfcheck")
    sub = ap.add_subparsers(required=True)
    for name, fn in [("validate", cmd_validate), ("audit", cmd_audit), ("plan", cmd_plan), ("run", cmd_run)]:
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
        p.set_defaults(func=fn)
        if name in {"audit", "plan", "run"}:
            p.add_argument("--feature")
        if name == "run":
            p.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if getattr(args, "feature", None) is None and args.func in {cmd_plan, cmd_run}:
        ap.error("--feature is required")
    args.func(args)

if __name__ == "__main__":
    main()
