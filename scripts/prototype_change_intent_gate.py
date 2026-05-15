#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path
from prototype_path_utils import resolve_under

ROOT = Path(__file__).resolve().parents[1]
SUBSTANTIAL = ROOT / "scripts" / "prototype_substantial_delta_gate.py"
VALID_INTENTS = {"bugfix", "hardening_pass", "convergence_iteration", "fresh_lane", "major_redesign"}
REQUIRE_SUBSTANTIAL = {"fresh_lane", "major_redesign"}

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")

def field(text: str, key: str) -> str:
    m = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", text, re.M)
    return m.group(1).strip() if m else ""

def finding(path: Path, msg: str) -> dict:
    return {"severity": "error", "path": str(path), "message": msg}

def run_substantial(previous: Path, candidate: Path, mode: str) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SUBSTANTIAL), "--previous", str(previous), "--candidate", str(candidate), "--mode", mode, "--format", "text"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return proc.returncode, proc.stdout.strip()

def main() -> int:
    ap = argparse.ArgumentParser(description="Bind requested prototype change intent to actual artifact delta.")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--intent", required=True, help="YAML-like change intent file relative to workflow")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()
    wf = Path(args.workflow).resolve()
    try:
        intent_path = resolve_under(wf, args.intent, "intent")
    except ValueError as exc:
        intent_path = wf / "<invalid-intent-path>"
        findings = [finding(wf, str(exc))]
        text = ""
    else:
        findings = []
    metrics: dict[str, object] = {}
    sub_output = ""
    if not intent_path.exists():
        findings.append(finding(intent_path, "change intent file missing"))
        text = ""
    else:
        text = read(intent_path)
    required = ["iteration_id", "model_lane", "previous_artifact", "candidate_artifact", "change_intent", "expected_delta_level", "must_preserve", "must_change"]
    for key in required:
        if not field(text, key) and f"{key}:" not in text:
            findings.append(finding(intent_path, f"change intent missing field: {key}"))
    intent = field(text, "change_intent")
    metrics["change_intent"] = intent
    if intent and intent not in VALID_INTENTS:
        findings.append(finding(intent_path, f"invalid change_intent: {intent}"))
    previous = None
    candidate = None
    if field(text, "previous_artifact"):
        try:
            previous = resolve_under(wf, field(text, "previous_artifact"), "previous_artifact")
        except ValueError as exc:
            findings.append(finding(intent_path, str(exc)))
    if field(text, "candidate_artifact"):
        try:
            candidate = resolve_under(wf, field(text, "candidate_artifact"), "candidate_artifact")
        except ValueError as exc:
            findings.append(finding(intent_path, str(exc)))
    if previous and not previous.exists():
        findings.append(finding(previous, "previous artifact missing"))
    if candidate and not candidate.exists():
        findings.append(finding(candidate, "candidate artifact missing"))
    if not findings and previous and candidate:
        mode = "new-iteration" if intent in REQUIRE_SUBSTANTIAL else "hardening-pass"
        code, sub_output = run_substantial(previous, candidate, mode)
        metrics["substantial_delta_exit_code"] = code
        metrics["substantial_delta_output"] = sub_output
        if intent in REQUIRE_SUBSTANTIAL and code != 0:
            findings.append(finding(intent_path, "requested fresh/major change but candidate looks like a small patch; mismatch diagnosis required"))
        if intent not in REQUIRE_SUBSTANTIAL and code == 0:
            metrics["classification"] = "small_delta_allowed"
    result = {"status": "PASS" if not findings else "FAIL", "metrics": metrics, "findings": findings}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']} intent={intent or 'UNKNOWN'} findings={len(findings)}")
        if sub_output:
            for line in sub_output.splitlines()[:12]: print("  " + line)
        for f in findings:
            print(f"ERROR: {f['path']}: {f['message']}")
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
