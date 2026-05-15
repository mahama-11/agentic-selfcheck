#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS = {
    "constraint-system": ROOT / "scripts" / "prototype_constraint_system_audit.py",
    "foundation": ROOT / "scripts" / "prototype_foundation_gate.py",
    "growth": ROOT / "scripts" / "prototype_foundation_growth_gate.py",
    "interaction-affordance": ROOT / "scripts" / "prototype_interaction_affordance_gate.py",
    "business-backbone": ROOT / "scripts" / "prototype_business_backbone_gate.py",
    "page-semantics": ROOT / "scripts" / "prototype_page_semantics_gate.py",
    "change-intent": ROOT / "scripts" / "prototype_change_intent_gate.py",
    "dual-model": ROOT / "scripts" / "prototype_dual_model_gate.py",
}


def run_check(name: str, cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return {"name": name, "exit_code": proc.returncode, "output": proc.stdout.strip(), "status": "PASS" if proc.returncode == 0 else "FAIL"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Single entrypoint for prototype foundation execution system.")
    ap.add_argument("--workflow", required=True, help="Prototype workflow directory")
    ap.add_argument("--delta", help="Candidate foundation growth delta file")
    ap.add_argument("--prototype", help="Candidate prototype HTML file")
    ap.add_argument("--iteration-delta", help="Candidate iteration delta file for non-regression/presentation gate")
    ap.add_argument("--interaction-prototype", help="Candidate prototype HTML file for interaction affordance gate")
    ap.add_argument("--business-backbone-prototype", help="Candidate prototype HTML file for business backbone gate")
    ap.add_argument("--business-backbone-delta", help="Business backbone delta file")
    ap.add_argument("--page-semantics", help="Page/module semantics decomposition for DOCX/screenshot-driven prototypes")
    ap.add_argument("--page-semantics-prototype", help="Candidate prototype HTML to compare against page semantics")
    ap.add_argument("--change-intent", help="Change intent file; binds requested magnitude to actual diff")
    ap.add_argument("--dual-current-prototype", help="Current model prototype HTML for mandatory dual-model lane gate")
    ap.add_argument("--dual-kimi-prototype", help="Kimi model prototype HTML for mandatory dual-model lane gate")
    ap.add_argument("--dual-current-delta", help="Current model lane delta/evidence file")
    ap.add_argument("--dual-kimi-delta", help="Kimi model lane delta/evidence file")
    ap.add_argument("--dual-comparison", help="Current-vs-Kimi comparison evidence file")
    ap.add_argument("--dual-current-origin", help="Current raw model origin evidence file")
    ap.add_argument("--dual-kimi-origin", help="Kimi raw model origin evidence file")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--foundation-only", action="store_true", help="Run only foundation/system checks; skip candidate prototype checks")
    args = ap.parse_args()

    workflow_path = Path(args.workflow).resolve()
    workflow = str(workflow_path)
    results: list[dict] = []

    results.append(run_check("constraint-system", [sys.executable, str(CHECKS["constraint-system"]), "--workflow", workflow, "--format", "text"]))

    foundation_cmd = [sys.executable, str(CHECKS["foundation"]), "--workflow", workflow, "--format", "text"]
    if args.prototype:
        foundation_cmd += ["--prototype", args.prototype]
    if args.iteration_delta:
        foundation_cmd += ["--delta", args.iteration_delta]
    results.append(run_check("foundation", foundation_cmd))

    if args.delta:
        results.append(run_check("growth", [sys.executable, str(CHECKS["growth"]), "--workflow", workflow, "--delta", args.delta, "--format", "text"]))
    elif not args.foundation_only:
        results.append({"name": "growth", "status": "FAIL", "exit_code": 2, "output": "missing --delta; candidate iterations must declare foundation growth"})

    if args.interaction_prototype:
        results.append(run_check("interaction-affordance", [sys.executable, str(CHECKS["interaction-affordance"]), "--workflow", workflow, "--prototype", args.interaction_prototype, "--format", "text"]))
    elif not args.foundation_only:
        results.append({"name": "interaction-affordance", "status": "FAIL", "exit_code": 2, "output": "missing --interaction-prototype; candidate prototypes must prove hover/tooltip/label/progress affordances"})

    if args.business_backbone_prototype and args.business_backbone_delta:
        results.append(run_check("business-backbone", [sys.executable, str(CHECKS["business-backbone"]), "--workflow", workflow, "--prototype", args.business_backbone_prototype, "--delta", args.business_backbone_delta, "--format", "text"]))
    elif not args.foundation_only:
        results.append({"name": "business-backbone", "status": "FAIL", "exit_code": 2, "output": "missing --business-backbone-prototype/--business-backbone-delta; candidate prototypes must prove preserved business backbone"})

    if args.page_semantics:
        cmd = [sys.executable, str(CHECKS["page-semantics"]), "--workflow", workflow, "--semantics", args.page_semantics, "--format", "text"]
        if args.page_semantics_prototype:
            cmd += ["--prototype", args.page_semantics_prototype]
        results.append(run_check("page-semantics", cmd))
    elif not args.foundation_only:
        results.append({"name": "page-semantics", "status": "FAIL", "exit_code": 2, "output": "missing --page-semantics; screenshot/DOCX prototypes must prove key image hierarchy and page/module semantics before presentation"})

    if args.change_intent:
        results.append(run_check("change-intent", [sys.executable, str(CHECKS["change-intent"]), "--workflow", workflow, "--intent", args.change_intent, "--format", "text"]))
    elif not args.foundation_only:
        results.append({"name": "change-intent", "status": "FAIL", "exit_code": 2, "output": "missing --change-intent; candidate prototypes must bind requested magnitude to actual diff"})

    dual_args = [
        args.dual_current_prototype,
        args.dual_kimi_prototype,
        args.dual_current_delta,
        args.dual_kimi_delta,
        args.dual_comparison,
        args.dual_current_origin,
        args.dual_kimi_origin,
    ]
    if all(dual_args):
        results.append(run_check("dual-model", [
            sys.executable, str(CHECKS["dual-model"]),
            "--workflow", workflow,
            "--current-prototype", args.dual_current_prototype,
            "--kimi-prototype", args.dual_kimi_prototype,
            "--current-delta", args.dual_current_delta,
            "--kimi-delta", args.dual_kimi_delta,
            "--comparison", args.dual_comparison,
            "--current-origin", args.dual_current_origin,
            "--kimi-origin", args.dual_kimi_origin,
            "--format", "text",
        ]))
    elif not args.foundation_only:
        missing = [
            name for name, value in [
                ("--dual-current-prototype", args.dual_current_prototype),
                ("--dual-kimi-prototype", args.dual_kimi_prototype),
                ("--dual-current-delta", args.dual_current_delta),
                ("--dual-kimi-delta", args.dual_kimi_delta),
                ("--dual-comparison", args.dual_comparison),
                ("--dual-current-origin", args.dual_current_origin),
                ("--dual-kimi-origin", args.dual_kimi_origin),
            ] if not value
        ]
        results.append({
            "name": "dual-model",
            "status": "FAIL",
            "exit_code": 2,
            "output": "missing " + ", ".join(missing) + "; serious prototype presentation requires synchronized Current + Kimi lanes",
        })

    status = "PASS" if all(r["status"] == "PASS" for r in results) else "FAIL"
    payload = {"status": status, "workflow": workflow, "results": results}
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"status={status} checks={len(results)}")
        for r in results:
            print(f"[{r['status']}] {r['name']}")
            if r["output"]:
                for line in r["output"].splitlines()[:40]:
                    print(f"  {line}")
    return 0 if status == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
