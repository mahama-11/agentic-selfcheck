#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import zlib
from pathlib import Path

import jsonschema

CASES = [
    ("good-before-user-presentation", "before-user-presentation", True),
    ("good-before-implementation", "before-implementation", True),
    ("good-before-final", "before-final", True),
    ("bad-missing-screenshot", "before-user-presentation", False),
    ("bad-url-as-screenshot", "before-user-presentation", False),
    ("bad-text-as-screenshot", "before-user-presentation", False),
    ("bad-manifest-arg-escape", "before-user-presentation", False),
    ("bad-path-escape", "before-implementation", False),
    ("bad-missing-human-signer", "before-implementation", False),
    ("bad-placeholder-freeze", "before-implementation", False),
    ("bad-missing-runtime", "before-final", False),
    ("bad-malformed-list", "before-final", False),
]


def png_bytes() -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    def chunk(t: bytes, d: bytes) -> bytes:
        return len(d).to_bytes(4, "big") + t + d + (zlib.crc32(t + d) & 0xffffffff).to_bytes(4, "big")
    ihdr = (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes([8, 6, 0, 0, 0])
    raw = b"\x00\x00\x00\x00\xff"
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def base_manifest(name: str) -> dict:
    return {
        "schema_version": "1.0",
        "workflow_id": name,
        "risk": "D",
        "project_adapter": "PROJECT_ADAPTER.yaml",
        "design_pack": ["DESIGN_BRIEF.md", "PROJECT_CONTEXT.md"],
        "lanes": [
            {"id": "lane-a", "artifact": "prototype-artifacts/prototype.html", "notes": "LANE_NOTES.md"}
        ],
        "screenshots": [
            {"surface": "home", "path": "prototype-screenshots/home.png"}
        ],
        "coverage": "PROTOTYPE_COVERAGE.md",
        "human_decision": {
            "decision": "ACCEPTED_WITH_NOTES",
            "artifact": "PROTOTYPE_ACCEPTANCE.md",
            "signer": "smoke reviewer",
            "signer_role": "product_owner",
            "decided_at": "2026-01-01T00:00:00Z",
            "decision_source": "smoke-test",
            "notes": "accepted smoke notes",
            "notes_closure": "all accepted-with-notes items are captured in parity plan and implementation contract"
        },
        "freeze": {"document": "PROTOTYPE_FREEZE.md", "payload": "prototype-freeze.json", "screenshots": ["prototype-screenshots/home.png"]},
        "parity_plan": "PROTOTYPE_PARITY_PLAN.md",
        "parity_report": "PARITY_REPORT.md",
        "runtime_evidence": ["runtime-evidence/browser-smoke.md"],
        "review_urls": ["https://example.invalid/review-only"],
    }


def write_common(wf: Path, manifest: dict) -> None:
    for d in ["prototype-artifacts", "prototype-screenshots", "runtime-evidence"]:
        (wf / d).mkdir(parents=True, exist_ok=True)
    files = {
        "PROJECT_ADAPTER.yaml": "project_root: /tmp/project\nframework: react\n",
        "DESIGN_BRIEF.md": "# Design Brief\n\nComplete smoke design brief.\n",
        "PROJECT_CONTEXT.md": "# Project Context\n\nEnough project context for manifest smoke.\n",
        "LANE_NOTES.md": "# Lane Notes\n\nSelected high-fidelity lane notes.\n",
        "prototype-artifacts/prototype.html": "<html><body>prototype</body></html>\n",
        "PROTOTYPE_COVERAGE.md": "# Prototype Coverage\n\n| Surface | Status |\n|---|---|\n| Home | PASS |\n",
        "PROTOTYPE_ACCEPTANCE.md": "# Prototype Acceptance\n\nDecision: ACCEPTED_WITH_NOTES\n",
        "PROTOTYPE_FREEZE.md": "# Prototype Freeze\n\nDecision: accepted\nOwner: smoke\nDate: 2026-01-01\nNon-negotiables: preserve layout, density, interactions.\n",
        "prototype-freeze.json": json.dumps({"approval": {"status": "human_approved"}}, indent=2),
        "PROTOTYPE_PARITY_PLAN.md": "# Prototype Parity Plan\n\n| Prototype surface | Production route/component | Data/API | Token/component mapping | Accepted deviation |\n|---|---|---|---|---|\n| Home | /home HomePage | existing API | token map | none |\n",
        "PARITY_REPORT.md": "# Parity Report\n\nStatus: PASS\nScreenshots compared.\n",
        "runtime-evidence/browser-smoke.md": "# Runtime Evidence\n\nStatus: PASS\nBrowser loaded without console errors.\n",
    }
    for rel, text in files.items():
        (wf / rel).write_text(text, encoding="utf-8")
    (wf / "prototype-screenshots/home.png").write_bytes(png_bytes())
    (wf / "FRONTEND_EVIDENCE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def write_fixture(root: Path, name: str) -> Path:
    wf = root / ".hermes/workflows/frontend-evidence-manifest-smoke" / name
    if wf.exists():
        shutil.rmtree(wf)
    wf.mkdir(parents=True, exist_ok=True)
    manifest = base_manifest(name)
    if name == "bad-missing-screenshot":
        manifest["screenshots"] = [{"surface": "home", "path": "prototype-screenshots/missing.png"}]
    elif name == "bad-url-as-screenshot":
        manifest["screenshots"] = [{"surface": "home", "path": "https://example.invalid/home.png"}]
    elif name == "bad-text-as-screenshot":
        pass
    elif name == "bad-manifest-arg-escape":
        pass
    elif name == "bad-path-escape":
        manifest["freeze"]["document"] = "../outside-freeze.md"
    elif name == "bad-missing-human-signer":
        manifest["human_decision"]["signer"] = None
    elif name == "bad-placeholder-freeze":
        pass
    elif name == "bad-missing-runtime":
        manifest["runtime_evidence"] = []
    elif name == "bad-malformed-list":
        manifest["runtime_evidence"] = "runtime-evidence/browser-smoke.md"
    write_common(wf, manifest)
    if name == "bad-placeholder-freeze":
        (wf / "PROTOTYPE_FREEZE.md").write_text("# Prototype Freeze\n\nTODO\n", encoding="utf-8")
    if name == "bad-text-as-screenshot":
        (wf / "prototype-screenshots/home.png").write_text("not really an image", encoding="utf-8")
    if name == "bad-manifest-arg-escape":
        outside = wf.parent / "outside_manifest_valid.json"
        outside.write_text((wf / "FRONTEND_EVIDENCE_MANIFEST.json").read_text(encoding="utf-8"), encoding="utf-8")
    return wf


def validate_template(root: Path) -> dict:
    schema = json.loads((root / "schemas/frontend-evidence-manifest.schema.json").read_text(encoding="utf-8"))
    template = json.loads((root / "templates/frontend/evidence-manifest/FRONTEND_EVIDENCE_MANIFEST.json").read_text(encoding="utf-8"))
    try:
        jsonschema.Draft202012Validator(schema).validate(template)
        return {"case": "schema-template", "expected": "PASS", "actual": "PASS", "returncode": 0, "stdout": "", "stderr": "", "ok": True}
    except Exception as exc:
        return {"case": "schema-template", "expected": "PASS", "actual": "FAIL", "returncode": 1, "stdout": "", "stderr": str(exc), "ok": False}


def run_case(root: Path, name: str, phase: str, should_pass: bool) -> dict:
    wf = write_fixture(root, name)
    cmd = ["scripts/frontend_evidence_manifest_gate.py", "--workflow", str(wf), "--phase", phase, "--format", "json"]
    if name == "bad-manifest-arg-escape":
        cmd.extend(["--manifest", "../outside_manifest_valid.json"])
    cp = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    passed = cp.returncode == 0
    no_traceback = "Traceback" not in cp.stdout and "Traceback" not in cp.stderr
    return {
        "case": name,
        "expected": "PASS" if should_pass else "FAIL",
        "actual": "PASS" if passed else "FAIL",
        "returncode": cp.returncode,
        "stdout": cp.stdout[-1600:],
        "stderr": cp.stderr[-1600:],
        "ok": passed == should_pass and no_traceback,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    results = [validate_template(root)] + [run_case(root, *case) for case in CASES]
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
