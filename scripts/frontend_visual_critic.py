#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

SCORE_MAP = {
    'product_comprehension': 'Product comprehension',
    'information_architecture': 'Information architecture',
    'visual_hierarchy': 'Visual hierarchy',
    'interaction_clarity': 'Interaction clarity',
    'state_coverage': 'State coverage',
    'design_system_fit': 'Design-system fit',
    'feasibility_against_real_apis_components': 'Feasibility against real APIs/components',
    'accessibility_responsiveness_baseline': 'Accessibility/responsiveness baseline',
    'distinctiveness_non_generic_quality': 'Distinctiveness / non-generic quality',
    'implementation_parity_readiness': 'Implementation parity readiness',
}
PASS_VERDICTS={'PASS','PASS_WITH_NOTES'}
PASS_DECISIONS={'ACCEPTED','ACCEPTED_WITH_NOTES'}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def validate_payload(data: dict) -> list[str]:
    errors=[]
    for key in ['schema_version','risk','workflow','image_evidence','verdict','scores','findings','required_changes','acceptance_decision']:
        if key not in data:
            errors.append(f'missing required field: {key}')
    if errors:
        return errors
    if data['schema_version'] != '1.0': errors.append('schema_version must be 1.0')
    if data['risk'] not in {'C','D'}: errors.append('risk must be C or D')
    if data['verdict'] not in {'PASS','PASS_WITH_NOTES','REQUEST_CHANGES','REJECT_DIRECTION'}: errors.append('invalid verdict')
    if data['acceptance_decision'] not in {'ACCEPTED','ACCEPTED_WITH_NOTES','REQUEST_CHANGES','REJECTED_DIRECTION'}: errors.append('invalid acceptance_decision')
    if not isinstance(data.get('image_evidence'), list) or not data['image_evidence']:
        errors.append('image_evidence must be non-empty')
    scores=data.get('scores') or {}
    missing=[k for k in SCORE_MAP if k not in scores]
    if missing:
        errors.append('missing scores: '+', '.join(missing))
    for k,v in scores.items():
        try:
            n=float(v)
        except Exception:
            errors.append(f'score {k} is not numeric')
            continue
        if not (1 <= n <= 5): errors.append(f'score {k} out of range 1-5')
    avg=sum(float(scores[k]) for k in SCORE_MAP if k in scores)/len(SCORE_MAP) if all(k in scores for k in SCORE_MAP) else None
    mn=min(float(scores[k]) for k in SCORE_MAP if k in scores) if all(k in scores for k in SCORE_MAP) else None
    threshold=4.2 if data.get('risk')=='D' else 3.8
    floor=3.5 if data.get('risk')=='D' else 3.0
    if avg is not None and avg < threshold: errors.append(f'average score {avg:.2f} below threshold {threshold:.1f}')
    if mn is not None and mn < floor: errors.append(f'min score {mn:.1f} below floor {floor:.1f}')
    if data.get('verdict') not in PASS_VERDICTS: errors.append('verdict is not passable')
    if data.get('acceptance_decision') not in PASS_DECISIONS: errors.append('acceptance_decision is not passable')
    return errors


def render_markdown(data: dict) -> tuple[str,str,str]:
    scores=data['scores']
    avg=sum(float(scores[k]) for k in SCORE_MAP)/len(SCORE_MAP)
    mn=min(float(scores[k]) for k in SCORE_MAP)
    findings='\n'.join([f"- **{f.get('severity','note')} / {f.get('dimension','general')}**: {f.get('message','')}" + (f" Recommendation: {f.get('recommendation')}" if f.get('recommendation') else '') for f in data.get('findings',[])]) or '- No findings.'
    changes='\n'.join([f'- {x}' for x in data.get('required_changes',[])]) or '- No required changes.'
    evidence='\n'.join([f"- `{x.get('path')}` ({x.get('kind')}{', '+x.get('viewport') if x.get('viewport') else ''})" for x in data.get('image_evidence',[])])
    critique=f'''# Design Critique\n\n## Critic verdict\n\n{data['verdict']}\n\n## Visual evidence reviewed\n\n{evidence}\n\n## Findings\n\n{findings}\n\n## Required changes before acceptance\n\n{changes}\n\n## Acceptance decision\n\n{data['acceptance_decision']}\n'''
    rows='\n'.join([f"| {label} | {float(scores[key]):.1f} | |" for key,label in SCORE_MAP.items()])
    scorecard=f'''# Prototype Scorecard\n\nScores are 1-5.\n\n| Dimension | Score | Notes |\n|---|---:|---|\n{rows}\n\n## Average score\n\n{avg:.2f}\n\n## Minimum score\n\n{mn:.1f}\n\n## Threshold\n\n- C-risk: average >= 3.8 and no dimension below 3\n- D-risk: average >= 4.2 and no dimension below 3.5\n\n## Decision\n\n{'PASS' if data['verdict'] in PASS_VERDICTS and data['acceptance_decision'] in PASS_DECISIONS else 'FAIL'}\n'''
    acceptance=f'''# Prototype Acceptance\n\n## Decision\n\n{data['acceptance_decision']}\n\n## Source\n\nGenerated from `visual-critique.json`.\n\n## Notes\n\n- Critic verdict: {data['verdict']}\n- Average score: {avg:.2f}\n- Minimum score: {mn:.1f}\n'''
    return critique, scorecard, acceptance


def prompt_text(workflow: Path, risk: str) -> str:
    return f'''You are an independent senior product design critic. Review the prototype screenshots for workflow `{workflow}` risk {risk}.\n\nReturn ONLY JSON matching `schemas/frontend-prototype-critique.schema.json`.\n\nScore 1-5 on all dimensions. Be strict: generic admin UI, weak IA, unclear actions, missing state coverage, or low feasibility should score low.\n\nRisk thresholds:\n- C: average >= 3.8 and no dimension below 3.0\n- D: average >= 4.2 and no dimension below 3.5, with human acceptance required\n\nRequired output fields: schema_version, risk, workflow, image_evidence, verdict, scores, findings, required_changes, acceptance_decision, human_review_required.\n'''


def main() -> int:
    ap=argparse.ArgumentParser(description='Validate and materialize structured visual critique into frontend prototype gate artifacts.')
    ap.add_argument('--workflow', required=True)
    ap.add_argument('--risk', choices=['C','D'], required=True)
    ap.add_argument('--input-json', help='Structured visual critique JSON')
    ap.add_argument('--write-artifacts', action='store_true', help='Write DESIGN_CRITIQUE.md, PROTOTYPE_SCORECARD.md, PROTOTYPE_ACCEPTANCE.md')
    ap.add_argument('--print-prompt', action='store_true')
    args=ap.parse_args()
    wf=Path(args.workflow).resolve()
    if args.print_prompt:
        print(prompt_text(wf, args.risk))
        return 0
    if not args.input_json:
        raise SystemExit('--input-json required unless --print-prompt')
    data=load_json(Path(args.input_json))
    errors=validate_payload(data)
    result={'status':'PASS' if not errors else 'FAIL','errors':errors,'input':str(args.input_json)}
    if args.write_artifacts and not errors:
        critique,scorecard,acceptance=render_markdown(data)
        (wf/'DESIGN_CRITIQUE.md').write_text(critique, encoding='utf-8')
        (wf/'PROTOTYPE_SCORECARD.md').write_text(scorecard, encoding='utf-8')
        (wf/'PROTOTYPE_ACCEPTANCE.md').write_text(acceptance, encoding='utf-8')
        result['written']=['DESIGN_CRITIQUE.md','PROTOTYPE_SCORECARD.md','PROTOTYPE_ACCEPTANCE.md']
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1

if __name__ == '__main__':
    raise SystemExit(main())
