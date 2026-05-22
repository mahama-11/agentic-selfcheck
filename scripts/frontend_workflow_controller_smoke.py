#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import jsonschema

CASES = [
    ("good-init", "init", True),
    ("good-final-pass", "FINAL_PASS", True),
    ("bad-missing-state", "status", False),
    ("bad-illegal-transition", "IMPLEMENTATION_READY", False),
    ("bad-tampered-final-from-intake", "FINAL_PASS", False),
    ("bad-malformed-nested-state", "IMPLEMENTATION_READY", False),
    ("bad-implementation-missing-human-signer", "IMPLEMENTATION_READY", False),
    ("bad-implementation-missing-freeze", "IMPLEMENTATION_READY", False),
    ("bad-implementation-placeholder-parity", "IMPLEMENTATION_READY", False),
    ("bad-final-missing-parity", "FINAL_PASS", False),
    ("bad-final-missing-runtime", "FINAL_PASS", False),
]


def png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"smoke-placeholder-png"


def base_state(name: str) -> dict:
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
            "artifact": "prototype-artifacts/prototype.html",
            "signer": "smoke reviewer",
            "signer_role": "product_owner",
            "decided_at": "2026-01-01T00:00:00Z",
            "decision_source": "smoke-test",
            "notes": "Smoke accepted direction with notes.",
            "notes_closure": "notes are captured in parity plan and implementation contract",
        },
        "freeze": {
            "document": "PROTOTYPE_FREEZE.md",
            "payload": "prototype-freeze.json",
            "frozen_screenshots": ["prototype-screenshots/home.png"],
        },
        "parity_plan": "PROTOTYPE_PARITY_PLAN.md",
        "parity_report": "PARITY_REPORT.md",
        "runtime_evidence": ["runtime-evidence/browser-smoke.md"],
    }


def write_common_files(wf: Path, state: dict) -> None:
    for d in ["prototype-artifacts", "prototype-screenshots", "runtime-evidence"]:
        (wf / d).mkdir(parents=True, exist_ok=True)
    (wf / "PROJECT_ADAPTER.yaml").write_text("project_root: /tmp/project\nframework: react\n", encoding="utf-8")
    (wf / "DESIGN_BRIEF.md").write_text("# Design Brief\n\nComplete enough for smoke.\n", encoding="utf-8")
    (wf / "PROTOTYPE_COVERAGE.md").write_text("# Coverage\n\n| Surface | Status |\n|---|---|\n| Home | PASS |\n", encoding="utf-8")
    (wf / "prototype-artifacts/prototype.html").write_text("<html><body>prototype</body></html>\n", encoding="utf-8")
    (wf / "prototype-screenshots/home.png").write_bytes(png_bytes())
    (wf / "PROTOTYPE_FREEZE.md").write_text("# Prototype Freeze\n\nDecision: accepted\nOwner: smoke\nDate: 2026-01-01\nNon-negotiables: preserve layout, interaction, density.\n", encoding="utf-8")
    (wf / "prototype-freeze.json").write_text(json.dumps({"selected_lane": "lane-a", "approval": {"status": "human_approved"}}, indent=2), encoding="utf-8")
    (wf / "PROTOTYPE_PARITY_PLAN.md").write_text("# Prototype Parity Plan\n\n| Prototype surface | Production route/component | Data/API | Token/component mapping | Accepted deviation |\n|---|---|---|---|---|\n| Home | /home / HomePage | existing service | token map | none |\n", encoding="utf-8")
    (wf / "PARITY_REPORT.md").write_text("# Parity Report\n\nStatus: PASS\nPrototype screenshot and production screenshot compared.\n", encoding="utf-8")
    (wf / "runtime-evidence/browser-smoke.md").write_text("# Browser Smoke\n\nStatus: PASS\nRoute loaded, console clean.\n", encoding="utf-8")
    (wf / "FRONTEND_WORKFLOW_STATE.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def write_fixture(root: Path, name: str) -> Path:
    wf = root / ".hermes/workflows/frontend-workflow-controller-smoke" / name
    if wf.exists():
        shutil.rmtree(wf)
    wf.mkdir(parents=True, exist_ok=True)
    if name == "bad-missing-state" or name == "good-init":
        return wf
    state = base_state(name)
    if name == "good-final-pass":
        state["state"] = "RUNTIME_VERIFIED"
        state["allowed_transitions"] = ["FINAL_PASS", "BLOCKED"]
    elif name == "bad-illegal-transition":
        state["state"] = "INTAKE"
        state["allowed_transitions"] = ["CONTEXT_READY", "BLOCKED"]
    elif name == "bad-tampered-final-from-intake":
        state["state"] = "INTAKE"
        state["allowed_transitions"] = ["FINAL_PASS"]
    elif name == "bad-malformed-nested-state":
        state["human_decision"] = "not-object"
        state["freeze"] = "not-object"
        state["runtime_evidence"] = "not-list"
    elif name == "bad-implementation-missing-human-signer":
        state["human_decision"]["signer"] = None
    elif name == "bad-implementation-missing-freeze":
        state["freeze"] = {"document": "PROTOTYPE_FREEZE.md", "payload": "prototype-freeze.json", "frozen_screenshots": []}
    elif name == "bad-implementation-placeholder-parity":
        pass
    elif name == "bad-final-missing-parity":
        state["state"] = "RUNTIME_VERIFIED"
        state["allowed_transitions"] = ["FINAL_PASS", "BLOCKED"]
        state["parity_report"] = "missing-parity.md"
    elif name == "bad-final-missing-runtime":
        state["state"] = "RUNTIME_VERIFIED"
        state["allowed_transitions"] = ["FINAL_PASS", "BLOCKED"]
        state["runtime_evidence"] = []
    write_common_files(wf, state)
    if name == "bad-implementation-placeholder-parity":
        (wf / "PROTOTYPE_PARITY_PLAN.md").write_text("# Prototype Parity Plan\n\n| Prototype surface | Production route/component | Data/API | Token/component mapping | Accepted deviation |\n|---|---|---|---|---|\n| TODO | TODO | TODO | TODO | |\n", encoding="utf-8")
    return wf


def run_case(root: Path, name: str, target: str, should_pass: bool) -> dict:
    wf = write_fixture(root, name)
    if target == "status":
        cmd = ["scripts/frontend_workflow_controller.py", "status", "--workflow", str(wf), "--format", "json"]
    elif target == "init":
        cmd = ["scripts/frontend_workflow_controller.py", "init", "--workflow", str(wf), "--workflow-id", name, "--risk", "D", "--format", "json"]
    else:
        cmd = ["scripts/frontend_workflow_controller.py", "check-transition", "--workflow", str(wf), "--to", target, "--format", "json"]
    cp = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    passed = cp.returncode == 0
    no_traceback = "Traceback" not in cp.stderr and "Traceback" not in cp.stdout
    ok = (passed == should_pass) and no_traceback
    return {
        "case": name,
        "expected": "PASS" if should_pass else "FAIL",
        "actual": "PASS" if passed else "FAIL",
        "returncode": cp.returncode,
        "stdout": cp.stdout[-1600:],
        "stderr": cp.stderr[-1600:],
        "ok": ok,
    }


def validate_template(root: Path) -> dict:
    schema = json.loads((root / "schemas/frontend-workflow-state.schema.json").read_text(encoding="utf-8"))
    template = json.loads((root / "templates/frontend/workflow-state/FRONTEND_WORKFLOW_STATE.json").read_text(encoding="utf-8"))
    try:
        jsonschema.Draft202012Validator(schema).validate(template)
        return {"case": "schema-template", "expected": "PASS", "actual": "PASS", "returncode": 0, "stdout": "", "stderr": "", "ok": True}
    except jsonschema.ValidationError as exc:
        return {"case": "schema-template", "expected": "PASS", "actual": "FAIL", "returncode": 1, "stdout": "", "stderr": str(exc), "ok": False}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    results = [validate_template(root)] + [run_case(root, *case) for case in CASES]
    ok = all(item["ok"] for item in results)
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
