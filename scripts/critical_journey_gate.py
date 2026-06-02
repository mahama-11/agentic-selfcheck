#!/usr/bin/env python3
"""Generic SelfCheck critical journey runner.

SelfCheck owns safe orchestration, redaction, project-root resolution, and report
layout. Product-specific behavior lives in adapter scripts declared by journey
YAML files under `journeys/`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml

SECRET_KEY_RE = re.compile(r"(password|passwd|secret|token|authorization|api[_-]?key|jwt)", re.I)
SAFE_PHASES = {"static", "api", "browser", "evidence"}


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def load_index(root: Path, folder: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted((root / folder).glob("*.yaml")):
        data = load_yaml(path)
        out[str(data["id"])] = data | {"__path": str(path)}
    return out


def redact_value(key: str, value: str) -> str:
    return "[REDACTED]" if SECRET_KEY_RE.search(key) and value else value


def redact_text(text: str, secrets: dict[str, str]) -> str:
    out = text or ""
    for key, value in secrets.items():
        if value and (SECRET_KEY_RE.search(key) or len(value) >= 8):
            out = out.replace(value, "[REDACTED]")
    out = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+\-/=]{8,}", r"\1[REDACTED]", out)
    out = re.sub(r"(?i)(password|token|authorization)(\s*[=:]\s*)([^\s'\"`]+)", r"\1\2[REDACTED]", out)
    return out


def resolve_project_root(root: Path, journey: dict[str, Any]) -> Path:
    projects = load_index(root, "projects")
    project_id = str(journey.get("project") or "")
    if project_id not in projects:
        raise ValueError(f"journey {journey.get('id')} references missing project {project_id}")
    return Path(str(projects[project_id]["root"])).expanduser().resolve()


def resolve_secret_fixture(project_root: Path, fixture: dict[str, Any] | None) -> tuple[Path | None, dict[str, str]]:
    if not fixture:
        return None, {}
    raw = str(fixture.get("path") or "")
    if not raw:
        if fixture.get("required"):
            raise ValueError("secret_fixture.path is required")
        return None, {}
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = project_root / path
    if not path.exists():
        if fixture.get("required"):
            raise ValueError(f"secret fixture missing: {path}")
        return path, {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    missing = [key for key in fixture.get("required_keys", []) if not values.get(key)]
    if missing:
        raise ValueError("secret fixture missing required keys: " + ", ".join(missing))
    return path, values


def resolve_adapter_command(root: Path, command: str) -> list[str]:
    argv = shlex.split(command)
    if not argv:
        raise ValueError("adapter command is empty")
    script = Path(argv[0])
    if script.is_absolute() or ".." in script.parts:
        raise ValueError(f"unsafe adapter command path: {script}")
    script_path = (root / script).resolve()
    scripts_root = (root / "scripts").resolve()
    if scripts_root not in [script_path, *script_path.parents]:
        raise ValueError(f"unsafe adapter command escapes scripts directory: {script_path}")
    if not script_path.exists():
        raise ValueError(f"adapter script not found: {script_path}")
    return [str(script_path), *argv[1:]]


def infer_status(returncode: int, stdout: str, stderr: str) -> str:
    if returncode != 0:
        return "FAIL"
    text = "\n".join([stdout or "", stderr or ""])
    statuses = re.findall(r'"status"\s*:\s*"([A-Z_]+)"', text)
    if any(s in {"FAIL", "BLOCK", "BLOCKED", "NEEDS_REPAIR"} for s in statuses):
        return "FAIL"
    if "PASS_WITH_NOTES" in statuses or "PASS_WITH_NOTES" in text:
        return "PASS_WITH_NOTES"
    return "PASS"


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    journeys = load_index(root, "journeys")
    if args.journey not in journeys:
        raise ValueError(f"unknown journey: {args.journey}")
    journey = journeys[args.journey]
    phase = args.phase
    if phase not in SAFE_PHASES or phase not in set(journey.get("phases", [])):
        raise ValueError(f"phase {phase} is not declared for journey {args.journey}")
    project_root = resolve_project_root(root, journey)
    fixture_path, secrets = resolve_secret_fixture(project_root, journey.get("secret_fixture"))
    argv = resolve_adapter_command(root, journey["adapter"]["command"])
    report_dir = root / "reports" / "critical-journeys" / args.journey
    env = os.environ.copy()
    env.update(secrets)
    env.update({
        "SELFCHECK_ROOT": str(root),
        "SELFCHECK_JOURNEY_ID": args.journey,
        "SELFCHECK_JOURNEY_PHASE": phase,
        "SELFCHECK_PROJECT_ROOT": str(project_root),
        "SELFCHECK_REPORT_DIR": str(report_dir),
    })
    if fixture_path:
        env["SELFCHECK_AUTH_FIXTURE"] = str(fixture_path)
    if args.mode:
        env[journey.get("mode_env") or "SELFCHECK_JOURNEY_MODE"] = args.mode
    started = time.time()
    proc = subprocess.run(argv + ["--phase", phase], cwd=root, text=True, capture_output=True, timeout=args.timeout, env=env)
    status = infer_status(proc.returncode, proc.stdout, proc.stderr)
    report = {
        "journey": args.journey,
        "phase": phase,
        "status": status,
        "project": journey["project"],
        "project_root": str(project_root),
        "adapter_command": journey["adapter"]["command"],
        "duration_seconds": round(time.time() - started, 3),
        "exit_code": proc.returncode,
        "secret_fixture": {"path": str(fixture_path) if fixture_path else None, "loaded": bool(secrets), "keys": sorted(secrets)},
        "stdout_tail": redact_text(proc.stdout[-6000:], secrets),
        "stderr_tail": redact_text(proc.stderr[-6000:], secrets),
    }
    report_path = report_dir / f"{phase}.json"
    write_report(report_path, report)
    if "project" in journey.get("report_aliases", []):
        write_report(project_root / "reports" / "critical-journeys" / args.journey / f"{phase}.json", report)
    print(json.dumps({"status": status, "journey": args.journey, "phase": phase, "report_path": str(report_path)}, ensure_ascii=False))
    return 0 if status in {"PASS", "PASS_WITH_NOTES"} else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--journey", required=True)
    parser.add_argument("--phase", required=True, choices=sorted(SAFE_PHASES))
    parser.add_argument("--mode", default="")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    try:
        return run(args)
    except Exception as exc:
        print(f"CRITICAL_JOURNEY_GATE_FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
