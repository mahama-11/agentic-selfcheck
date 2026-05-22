#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Result:
    status: str
    workflow: str
    controller: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "workflow": self.workflow, "controller": self.controller, "manifest": self.manifest, "reasons": self.reasons}


def run_json(cmd: list[str], cwd: Path, timeout: int = 60) -> tuple[int, dict[str, Any] | None, str]:
    try:
        cp = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        return 124, None, f"subprocess timeout: {' '.join(cmd)}"
    except (FileNotFoundError, PermissionError, OSError) as exc:
        return 127, None, f"subprocess failed: {exc}"
    data = None
    if cp.stdout.strip():
        try:
            data = json.loads(cp.stdout)
        except Exception:
            data = {"raw_stdout": cp.stdout[-1600:]}
    err = cp.stderr[-1600:]
    return cp.returncode, data, err


def path_has_symlink(path: Path, stop: Path) -> bool:
    stop = stop.resolve()
    cur = path
    chain = [cur]
    while cur != stop and cur != cur.parent:
        cur = cur.parent
        chain.append(cur)
    return any(p.is_symlink() for p in chain)


def resolve_workflow(root: Path, raw: str) -> tuple[Path, str | None]:
    wf = Path(raw)
    if not wf.is_absolute():
        wf = root / wf
    governed = (root / ".hermes/workflows").resolve()
    resolved = wf.resolve()
    try:
        resolved.relative_to(governed)
    except Exception:
        return resolved, "workflow must stay under governed .hermes/workflows"
    if path_has_symlink(wf, governed):
        return resolved, "workflow path components must not be symlinked"
    return resolved, None


def check(workflow: Path, root: Path) -> Result:
    controller_cmd = ["scripts/frontend_workflow_controller.py", "check-transition", "--workflow", str(workflow), "--to", "IMPLEMENTATION_READY", "--format", "json"]
    manifest_cmd = ["scripts/frontend_evidence_manifest_gate.py", "--workflow", str(workflow), "--phase", "before-implementation", "--format", "json"]
    c_code, c_data, c_err = run_json(controller_cmd, root)
    m_code, m_data, m_err = run_json(manifest_cmd, root)
    reasons: list[str] = []
    if c_code != 0:
        reasons.append("workflow controller blocked IMPLEMENTATION_READY")
        if c_err:
            reasons.append(c_err)
    if m_code != 0:
        reasons.append("evidence manifest blocked before-implementation")
        if m_err:
            reasons.append(m_err)
    return Result("PASS" if c_code == 0 and m_code == 0 else "BLOCKED", str(workflow), c_data, m_data, reasons or ["before-implementation gate passed"])


def print_result(result: Result, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"status={result.status}")
        print(f"workflow={result.workflow}")
        for reason in result.reasons:
            print(f"reason={reason}")
        if result.controller:
            print("controller_status=" + str(result.controller.get("status")))
        if result.manifest:
            print("manifest_status=" + str(result.manifest.get("status")))


def main() -> int:
    ap = argparse.ArgumentParser(description="Hard stop before frontend implementation starts.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    workflow, workflow_err = resolve_workflow(root, args.workflow)
    if not root.exists() or not root.is_dir():
        result = Result("BLOCKED", str(workflow), reasons=["root directory does not exist"])
    elif workflow_err:
        result = Result("BLOCKED", str(workflow), reasons=[workflow_err])
    elif not (root / "scripts/frontend_workflow_controller.py").exists():
        result = Result("BLOCKED", str(workflow), reasons=["frontend workflow controller script missing under root"])
    elif not (root / "scripts/frontend_evidence_manifest_gate.py").exists():
        result = Result("BLOCKED", str(workflow), reasons=["frontend evidence manifest gate script missing under root"])
    elif not workflow.exists() or not workflow.is_dir():
        result = Result("BLOCKED", str(workflow), reasons=["workflow directory does not exist"])
    else:
        result = check(workflow, root)
    print_result(result, args.format)
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
