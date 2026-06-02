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
DEFAULT_ADOPTION_CONFIG = "config/requirement-trace-adoption.yaml"


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


def validate_evidence_status(path: Path) -> str | None:
    """Fail closed on JSON evidence that exists but reports a non-passing status."""
    if path.suffix.lower() != ".json":
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"evidence JSON is not readable/valid: {bounded_error(exc)}"
    if not isinstance(data, dict):
        return "evidence JSON must contain an object"
    status = data.get("status")
    if not isinstance(status, str):
        return "evidence JSON missing string status"
    if status not in {"PASS", "PASS_WITH_NOTES"}:
        return f"evidence JSON status is {status!r}, expected PASS or PASS_WITH_NOTES"
    exit_code = data.get("exit_code")
    if exit_code is not None and not (type(exit_code) is int and exit_code == 0):
        return f"evidence JSON exit_code is {exit_code!r}, expected integer 0"
    return None


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


def as_string_list(value: Any, field: str, path: Path) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{path}: {field} must be a non-empty list of strings")
    seen: set[str] = set()
    duplicates = sorted({item for item in value if item in seen or seen.add(item)})
    if duplicates:
        raise ValueError(f"{path}: {field} contains duplicate value(s): {', '.join(duplicates)}")
    return list(value)


def load_adoption_config(root: Path, config_path: str | None) -> tuple[list[str], list[str], str, Path | None, list[Issue]]:
    """Load required-ledger adoption defaults.

    Missing default config preserves the original two-ledger fallback. Explicitly
    supplied config paths and malformed configs fail closed.
    """
    issues: list[Issue] = []
    raw_path = config_path or DEFAULT_ADOPTION_CONFIG
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        if config_path:
            issues.append(Issue("ERROR", str(path), "adoption config does not exist"))
        return list(DEFAULT_REQUIRED_LEDGERS), [], "config/v-business-gate-selector.yaml", path, issues
    try:
        data = load_yaml(path)
        required_ledgers = as_string_list(data.get("required_ledgers"), "required_ledgers", path)
        high_risk_features = as_string_list(data.get("high_risk_selector_features"), "high_risk_selector_features", path)
        selector_config = data.get("selector_config", "config/v-business-gate-selector.yaml")
        if not isinstance(selector_config, str) or not selector_config:
            raise ValueError(f"{path}: selector_config must be a non-empty string")
    except Exception as exc:
        issues.append(Issue("ERROR", str(path), f"failed to load adoption config: {bounded_error(exc)}"))
        return [], [], "config/v-business-gate-selector.yaml", path, issues
    return required_ledgers, high_risk_features, selector_config, path, issues


def load_business_selector_features(root: Path, selector_config: str) -> tuple[set[str], list[Issue]]:
    raw_path = Path(selector_config).expanduser()
    path = raw_path if raw_path.is_absolute() else root / raw_path
    try:
        data = load_yaml(path)
    except Exception as exc:
        return set(), [Issue("ERROR", str(path), f"failed to load business gate selector: {bounded_error(exc)}")]
    features = data.get("features")
    if not isinstance(features, dict):
        return set(), [Issue("ERROR", str(path), "business gate selector features must be a mapping")]
    return {str(key) for key in features}, []


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


def validate_ledgers(
    root: Path,
    v_root: Path,
    required_ledgers: list[str],
    high_risk_selector_features: list[str] | None = None,
    selector_config: str = "config/v-business-gate-selector.yaml",
    adoption_config_path: Path | None = None,
    preflight_issues: list[Issue] | None = None,
) -> dict[str, Any]:
    issues: list[Issue] = []
    if preflight_issues:
        issues.extend(preflight_issues)
    high_risk_selector_features = high_risk_selector_features or []
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
            "adoption_config": str(adoption_config_path) if adoption_config_path else None,
            "required_ledgers": required_ledgers,
            "high_risk_selector_features": high_risk_selector_features,
            "checked_ledgers": [],
            "checked_requirements": 0,
            "issues": [issue.as_dict() for issue in issues],
        }
    feature_ids = load_feature_ids(root)
    selector_features: set[str] = set()
    if high_risk_selector_features:
        selector_features, selector_issues = load_business_selector_features(root, selector_config)
        issues.extend(selector_issues)
    ledger_paths = iter_ledgers(root)
    ledgers_by_id: dict[str, dict[str, Any]] = {}
    req_id_paths: dict[str, str] = {}
    checked_requirements = 0
    today = dt.date.today()

    for required_id in required_ledgers:
        expected_path = root / "requirement-traces" / f"{required_id}.yaml"
        if not expected_path.exists():
            issues.append(Issue("ERROR", str(expected_path), f"missing required ledger {required_id}"))

    for feature_id in high_risk_selector_features:
        if feature_id not in selector_features:
            issues.append(Issue("ERROR", selector_config, f"high-risk selector feature {feature_id} is missing"))

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
                if evidence_path is not None:
                    if not evidence_path.exists():
                        if not waiver_ok:
                            issues.append(Issue("ERROR", str(evidence_path), f"missing evidence for {req_id} without non-expired waiver"))
                    elif evidence_error := validate_evidence_status(evidence_path):
                        if not waiver_ok:
                            issues.append(Issue("ERROR", str(evidence_path), f"invalid evidence for {req_id}: {evidence_error}"))

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

    for feature_id in high_risk_selector_features:
        ledger = ledgers_by_id.get(feature_id)
        if ledger is None:
            issues.append(Issue("ERROR", str(root / "requirement-traces"), f"high-risk selector feature {feature_id} has no loaded matching ledger"))
        elif ledger.get("feature") != feature_id:
            issues.append(Issue("ERROR", str(ledger.get("__path", root / "requirement-traces")), f"high-risk ledger {feature_id} must reference matching feature {feature_id}"))

    status = "PASS" if not any(issue.level == "ERROR" for issue in issues) else "FAIL"
    return {
        "status": status,
        "root": str(root),
        "v_root": str(v_root),
        "adoption_config": str(adoption_config_path) if adoption_config_path else None,
        "required_ledgers": required_ledgers,
        "high_risk_selector_features": high_risk_selector_features,
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
    parser.add_argument(
        "--adoption-config",
        default=None,
        help=f"Adoption config path (default: {DEFAULT_ADOPTION_CONFIG}; missing default falls back to original two ledgers)",
    )
    parser.add_argument("--required-ledger", action="append", default=[], help="Required ledger id; may be passed more than once")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    root = Path(args.root).expanduser().resolve()
    v_root = Path(args.v_root).expanduser().resolve()
    config_ledgers, high_risk_selector_features, selector_config, adoption_config_path, config_issues = load_adoption_config(
        root, args.adoption_config
    )
    required_ledgers: list[str] = list(args.required_ledger) if args.required_ledger else config_ledgers
    report = validate_ledgers(
        root,
        v_root,
        required_ledgers,
        high_risk_selector_features,
        selector_config,
        adoption_config_path,
        config_issues,
    )

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
