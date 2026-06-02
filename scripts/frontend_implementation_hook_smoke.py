#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from frontend_before_implementation_smoke import write_fixture

CASES = [
    ("good-complete-workflow", "/root/work/v", "ecommerce-frontend/src/pages/ProductCenter.tsx", "good-ready", True),
    ("bad-incomplete-workflow", "/root/work/v", "ecommerce-frontend/src/pages/ProductCenter.tsx", "bad-manifest-blocked", False),
    ("bad-missing-workflow-auto-bootstrap", "/root/work/v", "ecommerce-frontend/src/pages/ProductCenter.tsx", None, False),
    ("bad-repo-relative-missing-workflow-auto-bootstrap", "/root/work/v/ecommerce-frontend", "src/pages/ProductCenter.tsx", None, False),
    ("bad-repo-relative-app-auto-bootstrap", "/root/work/v/ecommerce-frontend", "src/App.tsx", None, False),
    ("good-non-frontend-change", "/root/work/v", "docs/README.md", None, True),
    ("good-docs-src-components-not-frontend", "/root/work/v", "docs/src/components/example.tsx", None, True),
    ("good-backend-src-pages-not-frontend", "/root/work/v", "platform-backend/src/pages/foo.tsx", None, True),
    ("bad-unsafe-traversal", "/root/work/v", "../ecommerce-frontend/src/pages/evil.tsx", None, False),
    ("bad-external-workflow", "/root/work/v", "ecommerce-frontend/src/pages/ProductCenter.tsx", "external-good-ready", False),
]


def workflow_arg_for(root: Path, base: Path, fixture_name: str | None) -> list[str]:
    if not fixture_name:
        return []
    source_name = "good-ready" if fixture_name == "external-good-ready" else fixture_name
    fixture = write_fixture(root, source_name)
    if fixture_name == "external-good-ready":
        external = Path("/tmp/frontend-external-good-ready-workflow")
        if external.exists():
            shutil.rmtree(external)
        shutil.copytree(fixture, external)
        return ["--frontend-workflow", str(external)]
    wf = base / "workflow"
    shutil.copytree(fixture, wf)
    return ["--frontend-workflow", str(wf)]


def run_case(root: Path, name: str, repo_root: str, changed_file: str, fixture_name: str | None, should_pass: bool) -> dict:
    base = root / ".hermes/workflows/frontend-implementation-hook-smoke" / name
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True, exist_ok=True)
    workflow_arg = workflow_arg_for(root, base, fixture_name)
    cmd = [
        "scripts/v_continuous_governance_trigger.py",
        "--repo-root", repo_root,
        "--changed-file", changed_file,
        "--source", "git-hook",
        "--dry-run",
        "--timeout", "120",
        *workflow_arg,
    ]
    cp = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    passed = cp.returncode == 0
    no_traceback = "Traceback" not in cp.stdout and "Traceback" not in cp.stderr
    extra_ok = True
    parsed = None
    try:
        parsed = json.loads(cp.stdout) if cp.stdout.strip() else None
    except Exception:
        parsed = None
    if name in {"bad-missing-workflow-auto-bootstrap", "bad-repo-relative-missing-workflow-auto-bootstrap", "bad-repo-relative-app-auto-bootstrap"}:
        auto = parsed.get("frontend_auto_bootstrap") if isinstance(parsed, dict) else None
        gate = parsed.get("frontend_implementation_gate") if isinstance(parsed, dict) else None
        wf = Path(auto.get("workflow", "")) if isinstance(auto, dict) and auto.get("workflow") else None
        changed = gate.get("changed_files", []) if isinstance(gate, dict) else []
        extra_ok = (
            isinstance(auto, dict)
            and auto.get("status") == "PASS"
            and wf is not None
            and (wf / "FRONTEND_WORKFLOW_STATE.json").exists()
            and (wf / "FRONTEND_EVIDENCE_MANIFEST.json").exists()
            and (wf / "PROJECT_ADAPTER.yaml").exists()
            and isinstance(gate, dict)
            and gate.get("status") == "BLOCKED"
            and "workflow is required" not in str(gate.get("stderr", ""))
            and (name != "bad-repo-relative-missing-workflow-auto-bootstrap" or "ecommerce-frontend/src/pages/ProductCenter.tsx" in changed)
        )
    if name == "bad-external-workflow":
        gate = parsed.get("frontend_implementation_gate") if isinstance(parsed, dict) else None
        extra_ok = isinstance(gate, dict) and gate.get("status") == "BLOCKED" and "governed .hermes/workflows" in str(gate.get("stderr", ""))
    return {
        "case": name,
        "expected": "PASS" if should_pass else "FAIL",
        "actual": "PASS" if passed else "FAIL",
        "returncode": cp.returncode,
        "stdout": cp.stdout[-2600:],
        "stderr": cp.stderr[-2600:],
        "ok": passed == should_pass and no_traceback and extra_ok,
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
