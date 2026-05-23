#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema
import yaml

DEFAULT_REQUIRED_LEDGERS = (
    "platform-runtime-business-integration-safety",
    "platform-financial-business-consistency",
)


@dataclass
class Issue:
    level: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"level": self.level, "path": self.path, "message": self.message}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML object")
    return data


def load_schema(root: Path) -> dict[str, Any]:
    return json.loads((root / "schemas" / "requirement-trace.schema.json").read_text(encoding="utf-8"))


def bounded_error(exc: Exception, *, limit: int = 500) -> str:
    message = " ".join(str(exc).split())
    if not message:
        message = exc.__class__.__name__
    if len(message) > limit:
        return message[: limit - 3] + "..."
    return message


def iter_ledgers(root: Path) -> list[Path]:
    ledger_dir = root / "requirement-traces"
    if not ledger_dir.exists():
        return []
    return sorted(ledger_dir.glob("*.yaml"))


def is_under(path: Path, parent: Path) -> bool:
    try:
        resolved = path.resolve(strict=False)
        root = parent.resolve(strict=False)
    except OSError:
        return False
    return resolved == root or root in resolved.parents


def resolve_v_evidence_path(raw: str, v_root: Path) -> tuple[Path | None, str | None]:
    p = Path(raw).expanduser()
    if any(part == ".." for part in p.parts):
        return None, "path traversal is not allowed"
    if p.is_absolute():
        resolved = p
    elif raw.startswith("reports/") or raw.startswith(".hermes/workflows/"):
        resolved = v_root / p
    else:
        return None, "relative evidence paths must start with reports/ or .hermes/workflows/"
    reports_root = v_root / "reports"
    workflows_root = v_root / ".hermes" / "workflows"
    if not (is_under(resolved, reports_root) or is_under(resolved, workflows_root)):
        return None, "evidence path must resolve under V reports/ or .hermes/workflows/"
    return resolved, None


def resolve_workflow_path(raw: str, v_root: Path) -> tuple[Path | None, str | None]:
    p = Path(raw).expanduser()
    if any(part == ".." for part in p.parts):
        return None, "path traversal is not allowed"
    resolved = p if p.is_absolute() else v_root / p
    workflows_root = v_root / ".hermes" / "workflows"
    if not is_under(resolved, workflows_root):
        return None, "workflow path must resolve under V .hermes/workflows/"
    return resolved, None


def load_feature_ids(root: Path) -> set[str]:
    features = set()
    for path in sorted((root / "features").glob("*.yaml")):
        try:
            data = load_yaml(path)
            fid = data.get("id")
            if isinstance(fid, str):
                features.add(fid)
        except Exception:
            # selfcheck validate owns feature schema diagnostics; this smoke only
            # needs enough information to fail closed on missing ledger gates.
            continue
    return features


def parse_non_expired_waiver(waiver: Any, today: dt.date) -> tuple[bool, str | None]:
    if waiver is None:
        return False, None
    if not isinstance(waiver, dict):
        return False, "waiver must be null or an object"
    missing = [key for key in ("owner", "reason", "expires") if not waiver.get(key)]
    if missing:
        return False, f"waiver missing required field(s): {', '.join(missing)}"
    try:
        expires = dt.date.fromisoformat(str(waiver["expires"]))
    except ValueError:
        return False, "waiver expires must be a valid YYYY-MM-DD date"
    if expires < today:
        return False, f"waiver expired on {expires.isoformat()}"
    return True, None


def validate_ledgers(root: Path, v_root: Path, required_ledgers: list[str]) -> dict[str, Any]:
    issues: list[Issue] = []
    schema_path = root / "schemas" / "requirement-trace.schema.json"
    try:
        schema = load_schema(root)
        validator_cls = jsonschema.validators.validator_for(schema)
        validator_cls.check_schema(schema)
        schema_validator = validator_cls(schema)
    except Exception as exc:
        issues.append(Issue("ERROR", str(schema_path), f"failed to load requirement trace schema: {bounded_error(exc)}"))
        return {
            "status": "FAIL",
            "root": str(root),
            "v_root": str(v_root),
            "required_ledgers": required_ledgers,
            "checked_ledgers": [],
            "checked_requirements": 0,
            "issues": [issue.as_dict() for issue in issues],
        }
    feature_ids = load_feature_ids(root)
    ledger_paths = iter_ledgers(root)
    ledgers_by_id: dict[str, dict[str, Any]] = {}
    req_id_paths: dict[str, str] = {}
    checked_requirements = 0
    today = dt.date.today()

    for required_id in required_ledgers:
        expected_path = root / "requirement-traces" / f"{required_id}.yaml"
        if not expected_path.exists():
            issues.append(Issue("ERROR", str(expected_path), f"missing required ledger {required_id}"))

    for path in ledger_paths:
        try:
            ledger = load_yaml(path)
            schema_validator.validate(ledger)
        except Exception as exc:
            issues.append(Issue("ERROR", str(path), bounded_error(exc)))
            continue

        ledger_id = str(ledger.get("id", ""))
        if ledger_id in ledgers_by_id:
            issues.append(Issue("ERROR", str(path), f"duplicate ledger id {ledger_id}"))
        ledgers_by_id[ledger_id] = ledger | {"__path": str(path)}
        if ledger_id != path.stem:
            issues.append(Issue("ERROR", str(path), f"ledger id '{ledger_id}' does not match filename '{path.stem}'"))

        workflow_path, workflow_error = resolve_workflow_path(str(ledger.get("workflow", "")), v_root)
        if workflow_error:
            issues.append(Issue("ERROR", str(path), f"invalid workflow path: {workflow_error}"))
        elif workflow_path is not None and not workflow_path.exists():
            issues.append(Issue("ERROR", str(workflow_path), f"ledger workflow does not exist for {ledger_id}"))

        feature = str(ledger.get("feature", ""))
        if feature not in feature_ids:
            issues.append(Issue("ERROR", str(path), f"ledger feature references missing SelfCheck feature {feature}"))

        for req in ledger.get("requirements", []):
            checked_requirements += 1
            req_id = str(req.get("id", ""))
            req_path = f"{path}#{req_id}"
            if req_id in req_id_paths:
                issues.append(Issue("ERROR", req_path, f"duplicate requirement id {req_id}; first seen at {req_id_paths[req_id]}"))
            else:
                req_id_paths[req_id] = req_path

            waiver_ok, waiver_error = parse_non_expired_waiver(req.get("waiver"), today)
            if waiver_error:
                issues.append(Issue("ERROR", req_path, waiver_error))

            for gate in req.get("affected_gates", []):
                if gate not in feature_ids:
                    issues.append(Issue("ERROR", req_path, f"affected gate references missing SelfCheck feature {gate}"))

            for raw_evidence in req.get("evidence_paths", []):
                evidence_path, evidence_error = resolve_v_evidence_path(str(raw_evidence), v_root)
                if evidence_error:
                    issues.append(Issue("ERROR", req_path, f"invalid evidence path {raw_evidence!r}: {evidence_error}"))
                    continue
                if evidence_path is not None and not evidence_path.exists() and not waiver_ok:
                    issues.append(Issue("ERROR", str(evidence_path), f"missing evidence for {req_id} without non-expired waiver"))

            for raw_workflow_evidence in req.get("workflow_evidence", []):
                workflow_evidence, workflow_evidence_error = resolve_v_evidence_path(str(raw_workflow_evidence), v_root)
                if workflow_evidence_error:
                    issues.append(Issue("ERROR", req_path, f"invalid workflow evidence path {raw_workflow_evidence!r}: {workflow_evidence_error}"))
                    continue
                if workflow_evidence is not None and not workflow_evidence.exists() and not waiver_ok:
                    issues.append(Issue("ERROR", str(workflow_evidence), f"missing workflow evidence for {req_id} without non-expired waiver"))

    for required_id in required_ledgers:
        if required_id not in ledgers_by_id:
            issues.append(Issue("ERROR", str(root / "requirement-traces"), f"required ledger id {required_id} not loaded"))

    status = "PASS" if not any(issue.level == "ERROR" for issue in issues) else "FAIL"
    return {
        "status": status,
        "root": str(root),
        "v_root": str(v_root),
        "required_ledgers": required_ledgers,
        "checked_ledgers": sorted(ledgers_by_id),
        "checked_requirements": checked_requirements,
        "issues": [issue.as_dict() for issue in issues],
    }


def print_text(report: dict[str, Any]) -> None:
    if report["status"] == "PASS":
        print(
            f"PASS: requirement trace ledgers checked "
            f"({len(report['checked_ledgers'])} ledgers, {report['checked_requirements']} requirements)"
        )
        return
    print("FAIL: requirement trace ledger smoke found issues")
    for issue in report["issues"]:
        print(f"{issue['level']}: {issue['path']}: {issue['message']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-closed smoke check for requirement trace ledgers.")
    parser.add_argument("--root", default=".", help="Agentic SelfCheck repository root")
    parser.add_argument("--v-root", default="/root/work/v", help="V workspace root for reports/ and .hermes/workflows/ evidence")
    parser.add_argument("--required-ledger", action="append", default=[], help="Required ledger id; may be passed more than once")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    v_root = Path(args.v_root).expanduser().resolve()
    required_ledgers: list[str] = list(args.required_ledger) if args.required_ledger else list(DEFAULT_REQUIRED_LEDGERS)
    report = validate_ledgers(root, v_root, required_ledgers)

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
