#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

CASES=[
    (['scripts/frontend_design_lane_gate.py','--root','.','--format','json'], True, 'base'),
    (['scripts/frontend_design_lane_gate.py','--root','.','--workflow','.hermes/workflows/frontend-design-lane-generation-smoke/good-c','--risk','C','--format','json'], True, 'good-c'),
    (['scripts/frontend_design_lane_gate.py','--root','.','--workflow','.hermes/workflows/frontend-design-lane-generation-smoke/good-d','--risk','D','--format','json'], True, 'good-d'),
    (['scripts/frontend_design_lane_gate.py','--root','.','--workflow','.hermes/workflows/frontend-design-lane-generation-smoke/bad-d-one-lane','--risk','D','--format','json'], False, 'bad-d-one-lane'),
    (['scripts/frontend_design_lane_gate.py','--root','.','--workflow','.hermes/workflows/frontend-design-lane-generation-smoke/bad-missing-screenshot','--risk','C','--format','json'], False, 'bad-missing-screenshot'),
    (['scripts/frontend_design_lane_gate.py','--root','.','--workflow','.hermes/workflows/frontend-design-lane-generation-smoke/bad-header-only-image','--risk','C','--format','json'], False, 'bad-header-only-image'),
    (['scripts/frontend_design_lane_gate.py','--root','.','--workflow','.hermes/workflows/frontend-design-lane-generation-smoke/bad-no-idat-image','--risk','C','--format','json'], False, 'bad-no-idat-image'),
    (['scripts/frontend_design_lane_gate.py','--root','.','--workflow','.hermes/workflows/frontend-design-lane-generation-smoke/bad-fake-webp-image','--risk','C','--format','json'], False, 'bad-fake-webp-image'),
    (['scripts/frontend_design_lane_gate.py','--root','.','--workflow','.hermes/workflows/frontend-design-lane-generation-smoke/bad-invalid-filter-png','--risk','C','--format','json'], False, 'bad-invalid-filter-png'),
    (['scripts/frontend_design_lane_gate.py','--root','.','--workflow','.hermes/workflows/frontend-design-lane-generation-smoke/bad-invalid-ihdr-png','--risk','C','--format','json'], False, 'bad-invalid-ihdr-png'),
    (['scripts/frontend_design_lane_gate.py','--root','.','--workflow','.hermes/workflows/frontend-design-lane-generation-smoke/bad-fake-jpeg-image','--risk','C','--format','json'], False, 'bad-fake-jpeg-image'),
]

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    results=[]; ok=True
    for cmd, should_pass, name in CASES:
        cp=subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        passed=cp.returncode==0
        if passed != should_pass: ok=False
        results.append({'case':name,'expected':'PASS' if should_pass else 'FAIL','actual':'PASS' if passed else 'FAIL','returncode':cp.returncode,'stdout':cp.stdout[-1200:],'stderr':cp.stderr[-1200:]})
    result={'status':'PASS' if ok else 'FAIL','cases':results}
    if args.format=='json': print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']}")
        for r in results: print(f"{r['case']}: expected {r['expected']} actual {r['actual']}")
    return 0 if ok else 1
if __name__ == '__main__':
    raise SystemExit(main())
