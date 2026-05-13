#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, json, shutil, subprocess, zlib
from pathlib import Path

CASES = [
    ('good-c', 'C', True),
    ('good-d', 'D', True),
    ('bad-missing-selected-lane', 'C', False),
    ('bad-missing-screenshot-listed-no-fallback', 'C', False),
    ('bad-empty-frozen-screenshots', 'C', False),
    ('bad-invalid-png-screenshot', 'C', False),
    ('bad-external-path-traversal', 'C', False),
    ('bad-missing-accepted-prototype-fields', 'C', False),
    ('bad-missing-previous-acceptance-artifacts', 'C', False),
    ('bad-unmapped-component', 'C', False),
    ('bad-api-state-mapping-gap', 'C', False),
    ('bad-contract-needed-without-rationale', 'C', False),
    ('bad-missing-nested-required-fields', 'C', False),
    ('bad-unapproved-deviation', 'C', False),
    ('bad-d-missing-human-approval', 'D', False),
    ('bad-extra-field', 'C', False),
]


def png_bytes() -> bytes:
    sig=b'\x89PNG\r\n\x1a\n'
    def chunk(t: bytes, d: bytes) -> bytes:
        return len(d).to_bytes(4,'big') + t + d + (zlib.crc32(t+d) & 0xffffffff).to_bytes(4,'big')
    ihdr=(1).to_bytes(4,'big') + (1).to_bytes(4,'big') + bytes([8,6,0,0,0])
    raw=b'\x00\x22\x44\x66\xff'
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def base_payload(name: str, risk: str) -> dict:
    return {
        'schema_version': '1.0',
        'risk': risk,
        'workflow': name,
        'selected_lane': 'lane-a',
        'accepted_prototype': {'artifact_path': 'design-lanes/lane-a/prototype.html', 'acceptance_doc': 'PROTOTYPE_ACCEPTANCE.md', 'notes': 'Accepted by smoke fixture.'},
        'frozen_screenshots': [{'path': 'prototype-screenshots/home.png', 'screen': 'home'}],
        'component_mapping': [{'prototype_element': 'Hero CTA card', 'production_component': 'HeroCtaCard', 'status': 'mapped', 'rationale': 'Existing production component covers layout and interactions.'}],
        'api_state_mapping': [{'prototype_state': 'Dashboard success with empty secondary list', 'production_source': 'GET /api/dashboard + DashboardViewModel', 'status': 'mapped', 'rationale': 'Production model exposes the visible fields.'}],
        'implementation_contract': {'owner': 'frontend-platform', 'readiness': 'ready_for_implementation', 'scope': 'Build frozen home/dashboard screen to screenshot parity.', 'handoff_artifacts': ['prototype-freeze.json', 'PROTOTYPE_FREEZE.md'], 'open_questions': []},
        'deviations': [],
        'approval': {'owner': 'product-design', 'status': 'human_approved' if risk == 'D' else 'accepted', 'rationale': 'Smoke fixture approval.', 'date': '2026-01-01'}
    }


def write_fixture(root: Path, name: str, risk: str) -> None:
    wf=root/'.hermes/workflows/frontend-prototype-freeze-smoke'/name
    if wf.exists():
        shutil.rmtree(wf)
    for d in ['design-lanes/lane-a','prototype-screenshots','frozen-prototype']:
        (wf/d).mkdir(parents=True, exist_ok=True)
    (wf/'PROTOTYPE_ACCEPTANCE.md').write_text('# Prototype Acceptance\n\nDecision: ACCEPTED\n\nSubstantive smoke fixture acceptance text for prototype freeze testing.\n', encoding='utf-8')
    (wf/'visual-critique.json').write_text(json.dumps({'verdict':'PASS','notes':['ok','smoke fixture visual critique contains enough text to be nonempty for the gate']}), encoding='utf-8')
    (wf/'reference-aware-critique.json').write_text(json.dumps({'verdict':'PASS','notes':['ok','smoke fixture reference-aware critique contains enough text to be nonempty for the gate']}), encoding='utf-8')
    (wf/'design-lanes/lane-a/prototype.html').write_text('<html><body><main>Accepted prototype</main></body></html>\n' * 8, encoding='utf-8')
    (wf/'prototype-screenshots/home.png').write_bytes(png_bytes())
    data=base_payload(name, risk)
    if name == 'bad-missing-selected-lane':
        data['selected_lane'] = ''
    elif name == 'bad-missing-screenshot-listed-no-fallback':
        data['frozen_screenshots'] = [{'path': 'prototype-screenshots/missing.png', 'screen': 'home'}]
        # Keep home.png present to prove listed screenshot failures do not fall back to discovery.
    elif name == 'bad-empty-frozen-screenshots':
        data['frozen_screenshots'] = []
    elif name == 'bad-invalid-png-screenshot':
        (wf/'prototype-screenshots/home.png').write_text('not a png', encoding='utf-8')
    elif name == 'bad-external-path-traversal':
        external=Path('/tmp/frontend-prototype-freeze-external.png')
        external.write_bytes(png_bytes())
        data['selected_lane'] = '/tmp'
        data['frozen_screenshots'] = [{'path': str(external), 'screen': 'home'}]
    elif name == 'bad-missing-accepted-prototype-fields':
        data['accepted_prototype'] = {'notes': 'missing required artifact_path and acceptance_doc'}
    elif name == 'bad-missing-previous-acceptance-artifacts':
        (wf/'PROTOTYPE_ACCEPTANCE.md').unlink()
    elif name == 'bad-unmapped-component':
        data['component_mapping'] = [{'prototype_element': 'Hero CTA card', 'status': 'mapped', 'rationale': 'No component supplied.'}]
    elif name == 'bad-api-state-mapping-gap':
        data['api_state_mapping'] = [{'prototype_state': 'Dashboard success with empty secondary list', 'status': 'mapped', 'rationale': 'No production source supplied.'}]
    elif name == 'bad-contract-needed-without-rationale':
        data['api_state_mapping'] = [{'prototype_state': 'Dashboard loading skeleton', 'status': 'contract_needed'}]
    elif name == 'bad-missing-nested-required-fields':
        data['component_mapping'] = [{'prototype_element': 'Hero CTA card', 'production_component': 'HeroCtaCard', 'rationale': 'Status omitted to prove it is required.'}]
        data['api_state_mapping'] = [{'prototype_state': 'Dashboard success with empty secondary list', 'production_source': 'GET /api/dashboard + DashboardViewModel', 'rationale': 'Status omitted to prove it is required.'}]
        data['deviations'] = [{}]
    elif name == 'bad-unapproved-deviation':
        data['deviations'] = [{'description': 'Changed primary navigation placement.', 'material': True, 'approval_status': 'pending', 'rationale': 'Implementation convenience.'}]
    elif name == 'bad-d-missing-human-approval':
        data['approval']['status'] = 'accepted'
    elif name == 'bad-extra-field':
        data['unexpected'] = 'must fail closed'
    (wf/'prototype-freeze.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    (root/'.hermes/workflows/frontend-prototype-freeze-smoke').mkdir(parents=True, exist_ok=True)
    for name, risk, _ in CASES:
        write_fixture(root, name, risk)
    results=[]; ok=True
    base_cmd=['scripts/frontend_prototype_freeze_gate.py','--root','.','--format','json']
    cp=subprocess.run(base_cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    base_pass=cp.returncode == 0
    if not base_pass: ok=False
    results.append({'case':'base','expected':'PASS','actual':'PASS' if base_pass else 'FAIL','returncode':cp.returncode,'stdout':cp.stdout[-1600:],'stderr':cp.stderr[-1600:]})
    for name, risk, should_pass in CASES:
        wf=f'.hermes/workflows/frontend-prototype-freeze-smoke/{name}'
        cmd=['scripts/frontend_prototype_freeze_gate.py','--root','.','--workflow',wf,'--risk',risk,'--format','json']
        cp=subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
