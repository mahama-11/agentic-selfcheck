#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, subprocess, zlib
from pathlib import Path

CASES = [
    ('good-complete-coverage', 'C', True),
    ('bad-missing-coverage', 'C', False),
    ('bad-placeholder-coverage', 'C', False),
    ('bad-no-complete-coverage-row', 'C', False),
    ('bad-blocked-core-coverage', 'C', False),
    ('bad-incomplete-extra-row', 'C', False),
    ('bad-missing-row-screenshot', 'C', False),
    ('bad-coverage-path-traversal', 'C', False),
]

SCORE_DIMS = [
    'Product comprehension',
    'Information architecture',
    'Visual hierarchy',
    'Interaction clarity',
    'State coverage',
    'Design-system fit',
    'Feasibility against real APIs/components',
    'Accessibility/responsiveness baseline',
    'Distinctiveness / non-generic quality',
    'Implementation parity readiness',
]

DQP_FILES = [
    'REFERENCE_PACK.md', 'AESTHETIC_DIRECTION.md', 'ANTI_PATTERNS.md',
    'DESIGN_TOKENS_MAP.md', 'COMPONENT_INVENTORY.md', 'REFERENCE_SCREENSHOTS.md',
    'PROJECT_FRONTEND_RULES.md',
]

BASE_DOCS = [
    'CONTEXT_PACK.md', 'DESIGN_BRIEF.md', 'INTERACTION_MODEL.md',
    'STATE_MATRIX.md', 'VISUAL_ACCEPTANCE_CHECKLIST.md', 'DESIGN_CRITIQUE.md',
    'PROTOTYPE_SCORECARD.md', 'PROTOTYPE_ACCEPTANCE.md', 'PROTOTYPE_PARITY_PLAN.md',
]


def png_bytes() -> bytes:
    sig=b'\x89PNG\r\n\x1a\n'
    def chunk(t: bytes, d: bytes) -> bytes:
        return len(d).to_bytes(4,'big') + t + d + (zlib.crc32(t+d) & 0xffffffff).to_bytes(4,'big')
    ihdr=(1).to_bytes(4,'big') + (1).to_bytes(4,'big') + bytes([8,6,0,0,0])
    raw=b'\x00\x22\x44\x66\xff'
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


def reference_aware_payload(name: str, wf: Path, risk: str) -> dict:
    refs=['Linear workflow clarity', 'Shopify Admin commercial density']
    if risk == 'D': refs.append('Raycast command-first interactions')
    return {
        'schema_version':'1.0', 'risk':risk, 'workflow':name,
        'critique_source':'visual-critique.json',
        'design_quality_pack':{
            'reference_pack':'REFERENCE_PACK.md',
            'aesthetic_direction':'AESTHETIC_DIRECTION.md',
            'anti_patterns':'ANTI_PATTERNS.md',
            'design_tokens_map':'DESIGN_TOKENS_MAP.md',
            'component_inventory':'COMPONENT_INVENTORY.md',
            'project_frontend_rules':'PROJECT_FRONTEND_RULES.md',
        },
        'reference_alignment':{'references_used':refs,'borrowed_principles':['clear hierarchy','task-first navigation'],'not_copied_elements':['brand-specific assets'],'score':4.2},
        'aesthetic_alignment':{'score':4.2,'matches':['consistent high-fidelity SaaS prototype'],'gaps':[]},
        'anti_pattern_check':{'violations':[],'avoided':['single hero-only prototype','generic gradient dashboard'],'score':4.2},
        'token_component_fit':{'status':'aligned','score':4.1,'notes':['uses declared token/component direction']},
        'project_rules_alignment':{'score':4.2,'matched_rules':['prototype-first before implementation'],'violated_rules':[]},
        'verdict':'PASS', 'required_changes':[], 'average_context_score':4.18,
    }


def visual_critique_payload(name: str, risk: str) -> dict:
    scores={
        'product_comprehension':4.1,
        'information_architecture':4.1,
        'visual_hierarchy':4.1,
        'interaction_clarity':4.1,
        'state_coverage':4.1,
        'design_system_fit':4.1,
        'feasibility_against_real_apis_components':4.1,
        'accessibility_responsiveness_baseline':4.1,
        'distinctiveness_non_generic_quality':4.1,
        'implementation_parity_readiness':4.1,
    }
    return {
        'schema_version':'1.0','risk':risk,'workflow':name,
        'image_evidence':[{'path':'prototype-screenshots/home.png','kind':'prototype','viewport':'desktop'}],
        'verdict':'PASS','scores':scores,'findings':[],'required_changes':[],
        'acceptance_decision':'ACCEPTED','human_review_required':False,'average_score':4.1,'min_score':4.1,
    }


def scorecard() -> str:
    rows='\n'.join(f'| {dim} | 4.1 | smoke pass |' for dim in SCORE_DIMS)
    return '# Prototype Scorecard\n\n| Dimension | Score | Notes |\n|---|---:|---|\n' + rows + '\n'


def write_good_fixture(root: Path, name: str, risk: str) -> Path:
    wf=root/'.hermes/workflows/frontend-quality-gate-smoke'/name
    if wf.exists(): shutil.rmtree(wf)
    for d in ['prototype-screenshots','design-lanes/lane-a/screenshots','design-lanes/lane-a/visual-evidence','reference-screenshots']:
        (wf/d).mkdir(parents=True, exist_ok=True)
    (wf/'prototype-screenshots/home.png').write_bytes(png_bytes())
    (wf/'design-lanes/lane-a/screenshots/home.png').write_bytes(png_bytes())
    (wf/'reference-screenshots/ref-a.png').write_bytes(png_bytes())
    (wf/'design-lanes/lane-a/prototype.html').write_text('<html><body><main>Complete prototype</main></body></html>\n' * 8, encoding='utf-8')

    (wf/'REFERENCE_PACK.md').write_text('# Reference Pack\n\nexternal_reference_only: true\n\n| ID | Product | Principle |\n|---|---|---|\n| r1 | Linear | Clear workflow hierarchy |\n| r2 | Shopify Admin | Commercial table density |\n', encoding='utf-8')
    (wf/'AESTHETIC_DIRECTION.md').write_text('# Aesthetic Direction\n\nA high-fidelity product-workbench direction with mature SaaS hierarchy, restrained accents, consistent density, and no decorative-only surfaces.\n', encoding='utf-8')
    (wf/'ANTI_PATTERNS.md').write_text('# Anti Patterns\n\n| Anti-pattern | Why forbidden |\n|---|---|\n| One hero only | Does not prove route coverage |\n| Generic AI dashboard | Too templated |\n| Inconsistent cards | Breaks product quality |\n', encoding='utf-8')
    (wf/'DESIGN_TOKENS_MAP.md').write_text('# Design Tokens Map\n\ntokens_status: declared\n\n| Token type | Value | Usage |\n|---|---|---|\n| spacing | 8px scale | Layout rhythm |\n| color | neutral + blue accent | State hierarchy |\n', encoding='utf-8')
    (wf/'COMPONENT_INVENTORY.md').write_text('# Component Inventory\n\ncomponents_status: declared\n\n| Component | Source | Usage |\n|---|---|---|\n| Shell | prototype | Global navigation |\n| WorkbenchCard | prototype | Surface grouping |\n', encoding='utf-8')
    (wf/'REFERENCE_SCREENSHOTS.md').write_text('# Reference Screenshots\n\nexternal_reference_only: true\n\n- https://linear.app/\n- https://www.shopify.com/admin\n', encoding='utf-8')
    (wf/'PROJECT_FRONTEND_RULES.md').write_text('# Project Frontend Rules\n\n- Prototype gate must pass before production implementation.\n- Human-visible screenshots are required for visual acceptance.\n', encoding='utf-8')

    (wf/'CONTEXT_PACK.md').write_text('# Context Pack\n\nSmoke workflow proving complete prototype coverage enforcement for frontend quality gate.\n', encoding='utf-8')
    (wf/'DESIGN_BRIEF.md').write_text('# Design Brief\n\nRisk C. Build a complete high-fidelity prototype, not a single screen.\n', encoding='utf-8')
    (wf/'INTERACTION_MODEL.md').write_text('# Interaction Model\n\nUser enters the workbench, opens detail drawer, reviews states, and takes primary action.\n', encoding='utf-8')
    (wf/'STATE_MATRIX.md').write_text('# State Matrix\n\n| Surface | Default | Loading | Empty | Error | Permission | Long content | Mobile | Notes |\n|---|---|---|---|---|---|---|---|---|\n| Main page | shown | shown | shown | shown | n/a | shown | shown | covered |\n', encoding='utf-8')
    (wf/'VISUAL_ACCEPTANCE_CHECKLIST.md').write_text('# Visual Acceptance Checklist\n\n- [x] Information architecture is clear.\n- [x] Critical states are visible.\n- [x] Desktop and mobile are reviewed.\n', encoding='utf-8')
    (wf/'PROTOTYPE_COVERAGE.md').write_text('# Prototype Coverage\n\n| Surface / route | User job covered | Prototype artifact / URL | Screenshot path | Core interactions shown | States shown | Status |\n|---|---|---|---|---|---|---|\n| /home | Understand task and act | design-lanes/lane-a/prototype.html | prototype-screenshots/home.png | drawer, tabs, selected state | default/loading/empty/error/mobile | COMPLETE |\n\n| Interaction | Where shown | Evidence path | Status |\n|---|---|---|---|\n| Detail drawer | /home | prototype-screenshots/home.png | COMPLETE |\n', encoding='utf-8')
    (wf/'DESIGN_CRITIQUE.md').write_text('# Design Critique\n\nPASS\n\nThe prototype is complete enough for smoke validation and avoids core anti-patterns.\n', encoding='utf-8')
    (wf/'PROTOTYPE_SCORECARD.md').write_text(scorecard(), encoding='utf-8')
    (wf/'PROTOTYPE_ACCEPTANCE.md').write_text('# Prototype Acceptance\n\nACCEPTED\n\nSmoke accepted.\n', encoding='utf-8')
    (wf/'PROTOTYPE_PARITY_PLAN.md').write_text('# Prototype Parity Plan\n\nMap prototype route /home to production route and maintain visual hierarchy.\n', encoding='utf-8')
    (wf/'visual-critique.json').write_text(json.dumps(visual_critique_payload(name, risk), ensure_ascii=False, indent=2), encoding='utf-8')
    (wf/'reference-aware-critique.json').write_text(json.dumps(reference_aware_payload(name, wf, risk), ensure_ascii=False, indent=2), encoding='utf-8')

    lane=wf/'design-lanes/lane-a'
    (lane/'LANE_BRIEF.md').write_text('# Lane Brief\n\nA substantive lane for complete prototype coverage smoke validation with clear product direction and constraints.\n', encoding='utf-8')
    (lane/'PROTOTYPE_ARTIFACT.md').write_text('# Prototype Artifact\n\n- artifact_type: html\n- artifact_path_or_url: prototype.html\n- generated_at: 2026-01-01\n- source_prompt_path: LANE_BRIEF.md\n\n## What was produced\nComplete smoke prototype with one covered product route and interaction.\n\n## Known limitations\nSynthetic fixture only.\n', encoding='utf-8')
    (lane/'LANE_NOTES.md').write_text('# Lane Notes\n\n## Design Quality Pack alignment\nAligned with references and anti-patterns.\n\ndecision: keep\nrationale: Complete enough for smoke validation.\n', encoding='utf-8')
    return wf


def write_fixture(root: Path, name: str, risk: str) -> None:
    wf=write_good_fixture(root, name, risk)
    if name == 'bad-missing-coverage':
        (wf/'PROTOTYPE_COVERAGE.md').unlink()
    elif name == 'bad-placeholder-coverage':
        (wf/'PROTOTYPE_COVERAGE.md').write_text('# Prototype Coverage\n\n| Surface / route | User job covered | Prototype artifact / URL | Screenshot path | Core interactions shown | States shown | Status |\n|---|---|---|---|---|---|---|\n| TODO | TODO | TODO | TODO | TODO | TODO | TODO |\n', encoding='utf-8')
    elif name == 'bad-no-complete-coverage-row':
        (wf/'PROTOTYPE_COVERAGE.md').write_text('# Prototype Coverage\n\n| Surface / route | User job covered | Prototype artifact / URL | Screenshot path | Core interactions shown | States shown | Status |\n|---|---|---|---|---|---|---|\n| /home | Understand task | design-lanes/lane-a/prototype.html | prototype-screenshots/home.png | drawer | default | DRAFT |\n', encoding='utf-8')
    elif name == 'bad-blocked-core-coverage':
        (wf/'PROTOTYPE_COVERAGE.md').write_text('# Prototype Coverage\n\n| Surface / route | User job covered | Prototype artifact / URL | Screenshot path | Core interactions shown | States shown | Status |\n|---|---|---|---|---|---|---|\n| /home | Understand task | design-lanes/lane-a/prototype.html | prototype-screenshots/home.png | drawer | default | COMPLETE |\n| /detail | Review detail | missing.html | missing.png | drawer | error | BLOCKED |\n', encoding='utf-8')
    elif name == 'bad-incomplete-extra-row':
        (wf/'PROTOTYPE_COVERAGE.md').write_text('# Prototype Coverage\n\n| Surface / route | User job covered | Prototype artifact / URL | Screenshot path | Core interactions shown | States shown | Status |\n|---|---|---|---|---|---|---|\n| /home | Understand task | design-lanes/lane-a/prototype.html | prototype-screenshots/home.png | drawer | default | COMPLETE |\n| /settings | Configure product | missing.html | prototype-screenshots/home.png | form | default | DRAFT |\n', encoding='utf-8')
    elif name == 'bad-missing-row-screenshot':
        (wf/'PROTOTYPE_COVERAGE.md').write_text('# Prototype Coverage\n\n| Surface / route | User job covered | Prototype artifact / URL | Screenshot path | Core interactions shown | States shown | Status |\n|---|---|---|---|---|---|---|\n| /home | Understand task | design-lanes/lane-a/prototype.html | prototype-screenshots/missing.png | drawer | default | COMPLETE |\n', encoding='utf-8')
    elif name == 'bad-coverage-path-traversal':
        external=Path('/tmp/frontend-quality-gate-smoke-outside.png')
        external.write_bytes(png_bytes())
        (wf/'PROTOTYPE_COVERAGE.md').write_text(f'# Prototype Coverage\n\n| Surface / route | User job covered | Prototype artifact / URL | Screenshot path | Core interactions shown | States shown | Status |\n|---|---|---|---|---|---|---|\n| /home | Understand task | design-lanes/lane-a/prototype.html | {external} | drawer | default | COMPLETE |\n', encoding='utf-8')


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    (root/'.hermes/workflows/frontend-quality-gate-smoke').mkdir(parents=True, exist_ok=True)
    for name, risk, _ in CASES:
        write_fixture(root, name, risk)
    results=[]; ok=True
    base=subprocess.run(['scripts/frontend_quality_gate.py','--root','.','--format','json'], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    base_pass=base.returncode == 0
    if not base_pass: ok=False
    results.append({'case':'base','expected':'PASS','actual':'PASS' if base_pass else 'FAIL','returncode':base.returncode,'stdout':base.stdout[-1600:],'stderr':base.stderr[-1600:]})
    for name, risk, should_pass in CASES:
        wf=f'.hermes/workflows/frontend-quality-gate-smoke/{name}'
        cp=subprocess.run(['scripts/frontend_quality_gate.py','--root','.','--workflow',wf,'--risk',risk,'--format','json'], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        passed=cp.returncode == 0
        if passed != should_pass: ok=False
        results.append({'case':name,'expected':'PASS' if should_pass else 'FAIL','actual':'PASS' if passed else 'FAIL','returncode':cp.returncode,'stdout':cp.stdout[-1800:],'stderr':cp.stderr[-1800:]})
    outside=Path('/tmp/frontend-quality-gate-outside-root')
    outside.mkdir(parents=True, exist_ok=True)
    cp=subprocess.run(['scripts/frontend_quality_gate.py','--root','.','--workflow',str(outside),'--risk','C','--format','json'], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    passed=cp.returncode == 0
    if passed:
        ok=False
    results.append({'case':'bad-workflow-outside-root','expected':'FAIL','actual':'PASS' if passed else 'FAIL','returncode':cp.returncode,'stdout':cp.stdout[-1800:],'stderr':cp.stderr[-1800:]})
    result={'status':'PASS' if ok else 'FAIL','cases':results}
    if args.format == 'json': print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('status=' + result['status'])
        for r in results: print(f"{r['case']}: expected {r['expected']} actual {r['actual']}")
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
