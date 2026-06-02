#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import jsonschema

CASES = [
    ("good-bootstrap", ["--name", "Checkout Polish", "--risk", "D", "--project", "ecommerce-frontend", "--title", "Checkout Polish"], True),
    ("bad-existing-no-force", ["--name", "Existing Workflow", "--risk", "D", "--project", "ecommerce-frontend"], False),
    ("bad-unsafe-name", ["--name", "../escape", "--risk", "D", "--project", "ecommerce-frontend"], False),
    ("bad-unsupported-risk", ["--name", "Low Risk", "--risk", "B", "--project", "ecommerce-frontend"], False),
    ("bad-symlink-force", ["--name", "Symlink Escape", "--risk", "D", "--project", "ecommerce-frontend", "--force"], False),
    ("bad-yaml-injection", ["--name", "Yaml Injection", "--risk", "D", "--project", "safe\n  root: /tmp/injected"], False),
    ("bad-child-symlink-force", ["--name", "Child Symlink", "--risk", "D", "--project", "ecommerce-frontend", "--force"], False),
    ("bad-project-yaml-list", ["--name", "Project List", "--risk", "D", "--project", "[evil]"], False),
    ("bad-project-root-colon", ["--name", "Root Colon", "--risk", "D", "--project", "ecommerce-frontend", "--project-root", "foo: bar"], False),
    ("bad-project-root-yaml-list", ["--name", "Root List", "--risk", "D", "--project", "ecommerce-frontend", "--project-root", "[evil]"], False),
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_case(root: Path, name: str, extra: list[str], should_pass: bool) -> dict:
    smoke_root = root / ".hermes/workflows/frontend-workflow-bootstrap-smoke" / name
    if smoke_root.exists():
        shutil.rmtree(smoke_root)
    smoke_root.mkdir(parents=True, exist_ok=True)
    work_root = smoke_root / "selfcheck-root"
    shutil.copytree(root / "templates", work_root / "templates")
    shutil.copytree(root / "scripts", work_root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    (work_root / ".hermes/workflows").mkdir(parents=True, exist_ok=True)
    if name == "bad-existing-no-force":
        (work_root / ".hermes/workflows/existing-workflow").mkdir(parents=True)
        (work_root / ".hermes/workflows/existing-workflow/KEEP.md").write_text("do not overwrite\n", encoding="utf-8")
    if name == "bad-symlink-force":
        outside = smoke_root / "outside-target"
        outside.mkdir(parents=True, exist_ok=True)
        link = work_root / ".hermes/workflows/symlink-escape"
        link.symlink_to(outside, target_is_directory=True)
    if name == "bad-child-symlink-force":
        wf = work_root / ".hermes/workflows/child-symlink"
        wf.mkdir(parents=True, exist_ok=True)
        outside = smoke_root / "outside-readme.md"
        outside.write_text("outside\n", encoding="utf-8")
        (wf / "README.md").symlink_to(outside)
    cmd = ["scripts/frontend_workflow_bootstrap.py", "--root", str(work_root), *extra, "--format", "json"]
    try:
        cp = subprocess.run(cmd, cwd=work_root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        returncode = cp.returncode
        stdout = cp.stdout
        stderr = cp.stderr
    except Exception as exc:
        returncode = 127
        stdout = ""
        stderr = f"subprocess failed: {exc}"
    passed = returncode == 0
    no_traceback = "Traceback" not in stdout and "Traceback" not in stderr
    details = {}
    if passed:
        try:
            details = json.loads(cp.stdout)
        except json.JSONDecodeError:
            details = {"parse_error": cp.stdout[:500]}
        wf = Path(details.get("workflow", ""))
        required = [
            "README.md",
            "PROJECT_ADAPTER.yaml",
            "FRONTEND_WORKFLOW_STATE.json",
            "FRONTEND_EVIDENCE_MANIFEST.json",
            "EXISTING_PRODUCT_BASELINE.md",
            "API_BACKEND_FEASIBILITY_MAP.md",
            "PRODUCT_SURFACE_LANGUAGE_RULES.md",
            "PROTOTYPE_REQUIREMENT_TRACE.md",
            "PROTOTYPE_ITERATION_POLICY.md",
            "PROTOTYPE_COVERAGE.md",
            "PROTOTYPE_FREEZE.md",
            "PROTOTYPE_PARITY_PLAN.md",
        ]
        missing = [p for p in required if not (wf / p).exists()]
        state_ok = manifest_ok = False
        if wf.exists() and not missing:
            state = load_json(wf / "FRONTEND_WORKFLOW_STATE.json")
            manifest = load_json(wf / "FRONTEND_EVIDENCE_MANIFEST.json")
            jsonschema.validate(state, load_json(root / "schemas/frontend-workflow-state.schema.json"))
            jsonschema.validate(manifest, load_json(root / "schemas/frontend-evidence-manifest.schema.json"))
            state_ok = state["workflow_id"] == wf.name and state["risk"] == "D" and state["state"] == "INTAKE" and state["project_adapter"] == "PROJECT_ADAPTER.yaml"
            manifest_ok = manifest["workflow_id"] == wf.name and manifest["risk"] == "D" and manifest["project_adapter"] == "PROJECT_ADAPTER.yaml"
        details["missing_required"] = missing if passed else []
        details["state_ok"] = state_ok
        details["manifest_ok"] = manifest_ok
        passed = passed and not missing and state_ok and manifest_ok
    ok = passed == should_pass and no_traceback
    return {
        "case": name,
        "expected": "PASS" if should_pass else "FAIL",
        "actual": "PASS" if passed else "FAIL",
        "returncode": returncode,
        "stdout": stdout[-2200:],
        "stderr": stderr[-2200:],
        "details": details,
        "ok": ok,
    }


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
