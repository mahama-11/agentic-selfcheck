#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, shutil, subprocess, zlib
from pathlib import Path

CASES = [
    ('good-c', 'C', True),
    ('good-d', 'D', True),
    ('bad-missing-prototype-freeze', 'C', False),
    ('bad-missing-production-screenshot', 'C', False),
    ('bad-below-80-score', 'C', False),
    ('bad-over-100-score', 'C', False),
    ('bad-unapproved-material-deviation', 'C', False),
    ('bad-d-material-not-human-approved', 'D', False),
    ('bad-route-coverage-gap', 'C', False),
    ('bad-malformed-extra-top-field', 'C', False),
    ('bad-malformed-nested-extra-field', 'C', False),
    ('bad-fake-png-header-only', 'C', False),
    ('bad-path-traversal-production', 'C', False),
    ('bad-contract-needed-visual-bypass', 'C', False),
]


def png_bytes() -> bytes:
    sig=b'\x89PNG\r\n\x1a\n'
    def chunk(t: bytes, d: bytes) -> bytes:
        return len(d).to_bytes(4,'big') + t + d + (zlib.crc32(t+d) & 0xffffffff).to_bytes(4,'big')
    ihdr=(1).to_bytes(4,'big') + (1).to_bytes(4,'big') + bytes([8,6,0,0,0])
    raw=b'\x00\x22\x44\x66\xff'
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def freeze_payload(name: str, risk: str) -> dict:
    return {
        'schema_version': '1.0', 'risk': risk, 'workflow': name, 'selected_lane': 'lane-a',
        'accepted_prototype': {'artifact_path': 'design-lanes/lane-a/prototype.html', 'acceptance_doc': 'PROTOTYPE_ACCEPTANCE.md', 'notes': 'accepted'},
        'frozen_screenshots': [{'screen': 'home', 'path': 'prototype-screenshots/home.png'}],
        'component_mapping': [{'prototype_element': 'Hero', 'production_component': 'Hero', 'status': 'mapped', 'rationale': 'same'}],
        'api_state_mapping': [{'prototype_state': 'Loaded home', 'production_source': 'HomeViewModel', 'status': 'mapped', 'rationale': 'same'}],
        'implementation_contract': {'owner': 'frontend', 'readiness': 'ready_for_implementation', 'scope': 'home parity', 'handoff_artifacts': ['prototype-freeze.json'], 'open_questions': []},
        'deviations': [],
        'approval': {'owner': 'design', 'status': 'human_approved' if risk == 'D' else 'accepted', 'rationale': 'smoke', 'date': '2026-01-01'},
    }


def parity_payload(name: str, risk: str) -> dict:
    return {
        'schema_version': '1.0', 'risk': risk, 'workflow': name,
        'prototype_freeze_evidence': {'path': 'prototype-freeze.json', 'gate_result_path': 'frozen-prototype/prototype-freeze-gate-result.json', 'status': 'PASS'},
        'threshold': {'minimum_score': 80, 'scoring_basis': 'Structured human/agent parity score; CV diff not required yet.'},
        'overall_parity_score': 91,
        'verdict': 'PASS',
        'coverage': [{'route': '/', 'surface': 'home', 'prototype_screen': 'home', 'production_screenshot': 'production-screenshots/home.png', 'status': 'covered'}],
        'comparisons': [{'route': '/', 'surface': 'home', 'prototype_screen': 'home', 'prototype_screenshot': 'prototype-screenshots/home.png', 'production_screenshot': 'production-screenshots/home.png', 'parity_score': 91, 'status': 'pass', 'notes': 'smoke parity'}],
        'deviations': [],
        'contract_needed_exceptions': [{'scope': 'analytics event naming', 'visual_parity_scope': False, 'owner': 'frontend', 'approval_status': 'approved', 'rationale': 'Non-visual contract to be completed separately; visual parity remains enforced.'}],
        'approval': {'owner': 'design', 'status': 'human_approved' if risk == 'D' else 'accepted', 'rationale': 'smoke approval', 'date': '2026-01-01'},
    }


def write_fixture(root: Path, name: str, risk: str) -> None:
    wf=root/'.hermes/workflows/frontend-prototype-parity-smoke'/name
    if wf.exists(): shutil.rmtree(wf)
    for d in ['design-lanes/lane-a','prototype-screenshots','frozen-prototype','production-screenshots']:
        (wf/d).mkdir(parents=True, exist_ok=True)
    (wf/'design-lanes/lane-a/prototype.html').write_text('<html><body>home</body></html>\n' * 6, encoding='utf-8')
    (wf/'PROTOTYPE_ACCEPTANCE.md').write_text('# Prototype Acceptance\n\nDecision: ACCEPTED\n\nSmoke accepted.\n', encoding='utf-8')
    (wf/'prototype-screenshots/home.png').write_bytes(png_bytes())
    (wf/'production-screenshots/home.png').write_bytes(png_bytes())
    freeze=freeze_payload(name, risk)
    report=parity_payload(name, risk)
    if name == 'bad-route-coverage-gap':
        freeze['frozen_screenshots'].append({'screen': 'settings', 'path': 'prototype-screenshots/settings.png'})
        (wf/'prototype-screenshots/settings.png').write_bytes(png_bytes())
    if name != 'bad-missing-prototype-freeze':
        (wf/'prototype-freeze.json').write_text(json.dumps(freeze, ensure_ascii=False, indent=2), encoding='utf-8')
    gate_result={'status':'PASS','workflow': str(wf), 'smoke': True}
    (wf/'frozen-prototype/prototype-freeze-gate-result.json').write_text(json.dumps(gate_result), encoding='utf-8')
    if name == 'bad-missing-production-screenshot':
        (wf/'production-screenshots/home.png').unlink()
    elif name == 'bad-below-80-score':
        report['overall_parity_score'] = 79
        report['comparisons'][0]['parity_score'] = 79
    elif name == 'bad-over-100-score':
        report['overall_parity_score'] = 101
        report['comparisons'][0]['parity_score'] = 101
    elif name == 'bad-unapproved-material-deviation':
        report['deviations'] = [{'description': 'Hero layout changed materially.', 'material': True, 'approval_status': 'pending', 'rationale': 'Implementation convenience.'}]
        report['verdict'] = 'PASS_WITH_APPROVED_DEVIATIONS'
    elif name == 'bad-d-material-not-human-approved':
        report['deviations'] = [{'description': 'Hero layout changed materially.', 'material': True, 'approval_status': 'approved', 'rationale': 'Approved but not human-approved for D.'}]
        report['verdict'] = 'PASS_WITH_APPROVED_DEVIATIONS'
    elif name == 'bad-malformed-extra-top-field':
        report['unexpected'] = 'fail closed'
    elif name == 'bad-malformed-nested-extra-field':
        report['threshold']['extra'] = 'fail closed'
    elif name == 'bad-fake-png-header-only':
        (wf/'production-screenshots/home.png').write_bytes(b'\x89PNG\r\n\x1a\n')
    elif name == 'bad-path-traversal-production':
        external=Path('/tmp/frontend-parity-external.png')
        external.write_bytes(png_bytes())
        report['coverage'][0]['production_screenshot'] = str(external)
        report['comparisons'][0]['production_screenshot'] = str(external)
    elif name == 'bad-contract-needed-visual-bypass':
        report['contract_needed_exceptions'] = [{'scope': 'home visual layout', 'visual_parity_scope': True, 'owner': 'frontend', 'approval_status': 'approved', 'rationale': 'Trying to bypass visual parity.'}]
    (wf/'frontend-parity-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    (root/'.hermes/workflows/frontend-prototype-parity-smoke').mkdir(parents=True, exist_ok=True)
    for name, risk, _ in CASES: write_fixture(root, name, risk)
    results=[]; ok=True
    cp=subprocess.run(['scripts/frontend_prototype_parity_gate.py','--root','.','--format','json'], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    base_pass=cp.returncode == 0
    if not base_pass: ok=False
    results.append({'case':'base','expected':'PASS','actual':'PASS' if base_pass else 'FAIL','returncode':cp.returncode,'stdout':cp.stdout[-1600:],'stderr':cp.stderr[-1600:]})
    for name, risk, should_pass in CASES:
        wf=f'.hermes/workflows/frontend-prototype-parity-smoke/{name}'
        cp=subprocess.run(['scripts/frontend_prototype_parity_gate.py','--root','.','--workflow',wf,'--risk',risk,'--format','json'], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        passed=cp.returncode == 0
        if passed != should_pass: ok=False
        results.append({'case':name,'expected':'PASS' if should_pass else 'FAIL','actual':'PASS' if passed else 'FAIL','returncode':cp.returncode,'stdout':cp.stdout[-1800:],'stderr':cp.stderr[-1800:]})
    result={'status':'PASS' if ok else 'FAIL','cases':results}
    if args.format == 'json': print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('status=' + result['status'])
        for r in results: print(f"{r['case']}: expected {r['expected']} actual {r['actual']}")
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
