#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

REQUIRED_SYSTEM_FILES = [
    "FOUNDATION_LEDGER.md",
    "28-constraint-enforcement-model.md",
    "29-foundation-growth-closed-loop.md",
    "31-foundation-execution-contract.md",
    "32-dynamic-constraint-execution-system.md",
]

REQUIRED_PHRASES = {
    "31-foundation-execution-contract.md": ["Execution levels", "Current honest status"],
    "32-dynamic-constraint-execution-system.md": ["rule -> executable check", "Constraint lifecycle", "Definition of done for constraints"],
    "FOUNDATION_LEDGER.md": ["current_foundation_version", "Anti-patterns learned"],
}


def finding(severity: str, path: str, message: str) -> dict:
    return {"severity": severity, "path": path, "message": message}


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit whether prototype constraints have an execution-system wrapper, not just loose docs.")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()
    workflow = Path(args.workflow).resolve()
    findings: list[dict] = []
    for rel in REQUIRED_SYSTEM_FILES:
        path = workflow / rel
        if not path.exists() or path.stat().st_size < 80:
            findings.append(finding("error", str(path), "required execution-system artifact missing or empty"))
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for phrase in REQUIRED_PHRASES.get(rel, []):
            if phrase not in text:
                findings.append(finding("error", str(path), f"required execution-system phrase missing: {phrase}"))
    result = {"status": "PASS" if not findings else "FAIL", "workflow": str(workflow), "findings": findings}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']} findings={len(findings)}")
        for f in findings:
            print(f"{f['severity'].upper()}: {f['path']}: {f['message']}")
    return 0 if not findings else 1

if __name__ == "__main__":
    raise SystemExit(main())
