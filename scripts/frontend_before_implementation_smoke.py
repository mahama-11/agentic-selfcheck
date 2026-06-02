#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from frontend_evidence_manifest_smoke import base_manifest, png_bytes, write_common

CASES = [
    ("good-ready", True),
    ("bad-controller-blocked", False),
    ("bad-manifest-blocked", False),
    ("bad-root", False),
]


def state_for(name: str) -> dict:
    return {
        "schema_version": "1.0",
        "workflow_id": name,
        "risk": "D",
        "state": "FROZEN",
        "allowed_transitions": ["IMPLEMENTATION_READY", "BLOCKED"],
        "project_adapter": "PROJECT_ADAPTER.yaml",
        "design_pack": "DESIGN_BRIEF.md",
        "prototype_coverage": "PROTOTYPE_COVERAGE.md",
        "human_decision": {
            "decision": "ACCEPTED_WITH_NOTES",
            "artifact": "PROTOTYPE_ACCEPTANCE.md",
            "signer": "smoke reviewer",
            "signer_role": "product_owner",
            "decided_at": "2026-01-01T00:00:00Z",
            "decision_source": "smoke-test",
            "notes": "accepted smoke",
            "notes_closure": "notes captured in parity plan"
        },
        "freeze": {"document": "PROTOTYPE_FREEZE.md", "payload": "prototype-freeze.json", "frozen_screenshots": ["prototype-screenshots/home.png"]},
        "parity_plan": "PROTOTYPE_PARITY_PLAN.md",
        "parity_report": None,
        "runtime_evidence": [],
    }


def write_fixture(root: Path, name: str) -> Path:
    wf = root / ".hermes/workflows/frontend-before-implementation-smoke" / name
    if wf.exists():
        shutil.rmtree(wf)
    wf.mkdir(parents=True, exist_ok=True)
    manifest = base_manifest(name)
    write_common(wf, manifest)
    state = state_for(name)
    if name == "bad-controller-blocked":
        state["freeze"]["frozen_screenshots"] = []
    elif name == "bad-manifest-blocked":
        manifest["parity_plan"] = "PROTOTYPE_PARITY_PLAN.md"
        (wf / "PROTOTYPE_PARITY_PLAN.md").write_text("# Prototype Parity Plan\n\nTODO\n", encoding="utf-8")
        (wf / "FRONTEND_EVIDENCE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (wf / "FRONTEND_WORKFLOW_STATE.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return wf


def run_case(root: Path, name: str, should_pass: bool) -> dict:
    wf = write_fixture(root, name)
    cmd = ["scripts/frontend_before_implementation_gate.py", "--workflow", str(wf), "--format", "json"]
    if name == "bad-root":
        cmd.extend(["--root", "/tmp/nonexistent-agentic-selfcheck-root"])
    cp = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    passed = cp.returncode == 0
    no_traceback = "Traceback" not in cp.stdout and "Traceback" not in cp.stderr
    return {"case": name, "expected": "PASS" if should_pass else "FAIL", "actual": "PASS" if passed else "FAIL", "returncode": cp.returncode, "stdout": cp.stdout[-1600:], "stderr": cp.stderr[-1600:], "ok": passed == should_pass and no_traceback}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    results = [run_case(root, *case) for case in CASES]
    ok = all(r["ok"] for r in results)
    payload = {"status": "PASS" if ok else "FAIL", "cases": results}
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("status=" + payload["status"])
        for r in results:
            print(f"{r['case']}: expected {r['expected']} actual {r['actual']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
