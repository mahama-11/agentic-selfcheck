#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

BASE_REQUIRED = [
    'CONTEXT_PACK.md',
    'DESIGN_BRIEF.md',
    'INTERACTION_MODEL.md',
    'STATE_MATRIX.md',
    'VISUAL_ACCEPTANCE_CHECKLIST.md',
    'PROTOTYPE_COVERAGE.md',
    'DESIGN_CRITIQUE.md',
    'PROTOTYPE_SCORECARD.md',
    'PROTOTYPE_ACCEPTANCE.md',
    'PROTOTYPE_PARITY_PLAN.md',
]
D_REQUIRED = ['DESIGN_LANES.md', 'VARIANT_COMPARISON.md', 'HUMAN_SIGNOFF.md']
DOC_REQUIRED = ['docs/frontend-quality-loop.md']
TEMPLATE_DIR = 'templates/frontend/high-fidelity-prototype-gate'
SCORE_DIMENSIONS = [
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


def nonempty(path: Path) -> bool:
    try:
        return path.exists() and path.is_file() and path.stat().st_size > 40
    except OSError:
        return False


def finding(severity: str, path: str, message: str) -> dict:
    return {'severity': severity, 'path': path, 'message': message}


def check_base(root: Path) -> dict:
    findings=[]
    for rel in DOC_REQUIRED:
        if not nonempty(root/rel):
            findings.append(finding('error', rel, 'required generic frontend quality doc missing or empty'))
    for name in BASE_REQUIRED + D_REQUIRED:
        rel=f'{TEMPLATE_DIR}/{name}'
        if not nonempty(root/rel):
            findings.append(finding('error', rel, 'required high-fidelity prototype template missing or empty'))
    return {'status':'PASS' if not findings else 'FAIL','scope':'base','findings':findings}


def parse_scorecard(path: Path) -> tuple[list[dict], float | None, list[dict]]:
    findings=[]
    scores=[]
    if not nonempty(path):
        return [], None, [finding('error', str(path), 'prototype scorecard missing or empty')]
    text=path.read_text(encoding='utf-8', errors='replace')
    for dim in SCORE_DIMENSIONS:
        # Markdown table row like: | Product comprehension | 4.2 | notes |
        pattern = r'^\|\s*' + re.escape(dim) + r'\s*\|\s*([0-5](?:\.\d+)?)\s*\|'
        m=re.search(pattern, text, flags=re.MULTILINE|re.IGNORECASE)
        if not m:
            findings.append(finding('error', str(path), f'missing numeric score for dimension: {dim}'))
            continue
        value=float(m.group(1))
        if value <= 0 or value > 5:
            findings.append(finding('error', str(path), f'invalid score for {dim}: {value}'))
        scores.append({'dimension': dim, 'score': value})
    avg=sum(s['score'] for s in scores)/len(scores) if scores else None
    return scores, avg, findings


def count_design_lanes(path: Path) -> int:
    if not nonempty(path):
        return 0
    text=path.read_text(encoding='utf-8', errors='replace')
    count=0
    for line in text.splitlines():
        if re.match(r'^\|\s*[A-Z0-9][^|]*\|\s*[^|\s][^|]*\|\s*[^|\s][^|]*\|\s*[^|\s][^|]*\|', line):
            if 'Lane' not in line and '---' not in line:
                count+=1
    return count


ALLOWED_COVERAGE_STATUS={'COMPLETE','PASS','DONE'}
PLACEHOLDER_VALUES={'TODO','TBD','PLACEHOLDER','FILL','FILL_ME','N/A','NA','NONE','-','—','MISSING','BLOCKED','DRAFT','PARTIAL','INCOMPLETE'}


def is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def resolve_workflow_file(wf: Path, raw: str) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    raw=raw.strip()
    if raw.startswith(('http://','https://')):
        return None
    p=Path(raw)
    candidate=p if p.is_absolute() else wf/p
    try:
        resolved=candidate.resolve()
    except OSError:
        return None
    if not is_within(resolved, wf):
        return None
    return resolved if resolved.exists() and resolved.is_file() else None


def has_placeholder(cells: list[str]) -> bool:
    for cell in cells:
        normalized=cell.strip().upper()
        if normalized in PLACEHOLDER_VALUES:
            return True
        if any(token in normalized for token in ['TODO','TBD','PLACEHOLDER','FILL ME']):
            return True
    return False


def check_prototype_coverage(path: Path, wf: Path) -> list[dict]:
    findings=[]
    if not nonempty(path):
        return [finding('error', str(path), 'prototype coverage matrix missing or empty')]
    text=path.read_text(encoding='utf-8', errors='replace')
    surface_rows=[]; interaction_rows=[]
    section=None
    for line in text.splitlines():
        stripped=line.strip()
        if stripped.startswith('| Surface / route'):
            section='surface'; continue
        if stripped.startswith('| Interaction'):
            section='interaction'; continue
        if not stripped.startswith('|') or '---' in stripped:
            continue
        cells=[c.strip() for c in stripped.strip('|').split('|')]
        if section == 'surface' and len(cells) >= 7:
            surface_rows.append(cells)
        elif section == 'interaction' and len(cells) >= 4:
            interaction_rows.append(cells)
    rows=surface_rows + interaction_rows
    if not rows:
        findings.append(finding('error', str(path), 'prototype coverage must include at least one concrete surface or interaction row'))
        return findings
    for idx, cells in enumerate(surface_rows, start=1):
        if has_placeholder(cells):
            findings.append(finding('error', str(path), f'surface coverage row {idx} contains placeholder/incomplete values'))
        status=cells[6].strip().upper()
        if status not in ALLOWED_COVERAGE_STATUS:
            findings.append(finding('error', str(path), f'surface coverage row {idx} status must be COMPLETE/PASS/DONE, got {cells[6]!r}'))
        artifact=cells[2].strip()
        if not artifact.startswith(('http://','https://')) and resolve_workflow_file(wf, artifact) is None:
            findings.append(finding('error', str(path), f'surface coverage row {idx} artifact path must exist under workflow or be http(s) URL'))
        screenshot=resolve_workflow_file(wf, cells[3].strip())
        if screenshot is None or screenshot.suffix.lower() not in IMAGE_EXTS:
            findings.append(finding('error', str(path), f'surface coverage row {idx} screenshot path must exist under workflow and be an image'))
    for idx, cells in enumerate(interaction_rows, start=1):
        if has_placeholder(cells):
            findings.append(finding('error', str(path), f'interaction coverage row {idx} contains placeholder/incomplete values'))
        status=cells[3].strip().upper()
        if status not in ALLOWED_COVERAGE_STATUS:
            findings.append(finding('error', str(path), f'interaction coverage row {idx} status must be COMPLETE/PASS/DONE, got {cells[3]!r}'))
        evidence=resolve_workflow_file(wf, cells[2].strip())
        if evidence is None:
            findings.append(finding('error', str(path), f'interaction coverage row {idx} evidence path must exist under workflow'))
    return findings


def has_decision(path: Path, allowed: set[str]) -> bool:
    if not nonempty(path):
        return False
    text=path.read_text(encoding='utf-8', errors='replace').upper()
    return any(x in text for x in allowed)


IMAGE_EXTS={'.png','.jpg','.jpeg','.webp'}

def evidence_files(wf: Path) -> dict:
    buckets={'prototype': [], 'production': [], 'visual': [], 'browser': [], 'other': []}
    mapping={
        'prototype-screenshots':'prototype',
        'production-screenshots':'production',
        'visual-evidence':'visual',
        'browser-evidence':'browser',
        'screenshots':'other',
    }
    for rel,bucket in mapping.items():
        d=wf/rel
        if d.exists():
            for x in d.rglob('*'):
                if x.is_file() and x.name != '.gitkeep':
                    item={'path': str(x), 'ext': x.suffix.lower(), 'is_image': x.suffix.lower() in IMAGE_EXTS}
                    buckets[bucket].append(item)
    return buckets

def image_count(items: list[dict]) -> int:
    return sum(1 for x in items if x.get('is_image'))


def check_workflow(root: Path, workflow: Path, risk: str) -> dict:
    wf = workflow if workflow.is_absolute() else root/workflow
    risk=risk.upper()
    findings=[]
    if not wf.exists():
        findings.append(finding('error', str(wf), 'workflow directory does not exist'))
        return {'status':'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'findings':findings}
    try:
        wf=wf.resolve()
        root_resolved=root.resolve()
    except OSError:
        findings.append(finding('error', str(wf), 'workflow path cannot be resolved'))
        return {'status':'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'findings':findings}
    if not is_within(wf, root_resolved):
        findings.append(finding('error', str(wf), 'workflow directory must stay under --root'))
        return {'status':'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'findings':findings}

    required=list(BASE_REQUIRED)
    if risk == 'D':
        required += D_REQUIRED
    for name in required:
        p=wf/name
        if not nonempty(p):
            findings.append(finding('error', str(p), f'required artifact for risk {risk} missing or empty'))
    findings.extend(check_prototype_coverage(wf/'PROTOTYPE_COVERAGE.md', wf))

    critique_json=wf/'visual-critique.json'
    if not nonempty(critique_json):
        findings.append(finding('error', str(critique_json), 'structured visual critique JSON missing; run frontend_visual_critic.py after independent visual review'))
    reference_aware_result=None
    freeze_readiness=None
    reference_aware_json=wf/'reference-aware-critique.json'
    if not nonempty(reference_aware_json):
        findings.append(finding('error', str(reference_aware_json), 'reference-aware critique JSON missing; run frontend_reference_aware_critic.py after visual critique and Design Quality Pack'))
    else:
        try:
            from frontend_reference_aware_critic import validate_payload, load_json
            reference_aware_result={'status':'PASS','errors':[]}
            ra_errors=validate_payload(root, wf, risk, load_json(reference_aware_json))
            if ra_errors:
                reference_aware_result={'status':'FAIL','errors':ra_errors}
                findings.append(finding('error', str(reference_aware_json), 'reference-aware critique must PASS before prototype acceptance'))
                for err in ra_errors:
                    findings.append(finding('error', str(reference_aware_json), err))
        except Exception as exc:
            findings.append(finding('error', str(reference_aware_json), f'could not validate reference-aware critique: {exc}'))

    ev=evidence_files(wf)
    total_images=sum(image_count(v) for v in ev.values())
    proto_images=image_count(ev['prototype'])
    prod_images=image_count(ev['production'])
    visual_images=image_count(ev['visual']) + image_count(ev['browser']) + image_count(ev['other'])
    if total_images == 0:
        findings.append(finding('error', str(wf), 'no real image evidence found; expected .png/.jpg/.jpeg/.webp under prototype-screenshots, production-screenshots, visual-evidence, or browser-evidence'))
    if proto_images == 0:
        findings.append(finding('error', str(wf/'prototype-screenshots'), 'missing prototype screenshot image evidence'))
    if risk == 'D' and proto_images < 2:
        findings.append(finding('error', str(wf/'prototype-screenshots'), 'D-risk work requires at least two prototype screenshot images or variant screenshots'))

    scores, avg, score_findings = parse_scorecard(wf/'PROTOTYPE_SCORECARD.md')
    findings.extend(score_findings)
    min_score=min([s['score'] for s in scores], default=None)
    threshold = 4.2 if risk == 'D' else 3.8
    min_threshold = 3.5 if risk == 'D' else 3.0
    if avg is not None and avg < threshold:
        findings.append(finding('error', str(wf/'PROTOTYPE_SCORECARD.md'), f'average score {avg:.2f} below {risk}-risk threshold {threshold:.1f}'))
    if min_score is not None and min_score < min_threshold:
        findings.append(finding('error', str(wf/'PROTOTYPE_SCORECARD.md'), f'min dimension score {min_score:.1f} below {risk}-risk floor {min_threshold:.1f}'))

    if not has_decision(wf/'DESIGN_CRITIQUE.md', {'PASS', 'PASS_WITH_NOTES'}):
        findings.append(finding('error', str(wf/'DESIGN_CRITIQUE.md'), 'design critique must be PASS or PASS_WITH_NOTES before implementation'))
    if not has_decision(wf/'PROTOTYPE_ACCEPTANCE.md', {'ACCEPTED', 'ACCEPTED_WITH_NOTES'}):
        findings.append(finding('error', str(wf/'PROTOTYPE_ACCEPTANCE.md'), 'prototype acceptance must be ACCEPTED or ACCEPTED_WITH_NOTES'))

    lane_count = count_design_lanes(wf/'DESIGN_LANES.md') if (wf/'DESIGN_LANES.md').exists() else 0
    lane_gate_result=None
    try:
        from frontend_design_lane_gate import check_workflow as check_lane_workflow
        lane_gate_result=check_lane_workflow(root, wf, risk)
        if lane_gate_result.get('status') != 'PASS':
            findings.append(finding('error', str(wf/'design-lanes'), 'design lane gate must PASS before prototype acceptance'))
            for lf in lane_gate_result.get('findings', []):
                findings.append(finding(lf.get('severity','error'), lf.get('path',''), lf.get('message','design lane gate finding')))
        lane_count=max(lane_count, lane_gate_result.get('lane_count') or 0)
    except Exception as exc:
        findings.append(finding('error', str(wf/'design-lanes'), f'could not run design lane gate: {exc}'))
    if risk == 'D' and lane_count < 2:
        findings.append(finding('error', str(wf/'DESIGN_LANES.md'), 'D-risk frontend work requires at least two independent design lanes'))

    freeze_payload=wf/'prototype-freeze.json'
    if freeze_payload.exists():
        try:
            from frontend_prototype_freeze_gate import check_workflow as check_freeze_workflow
            freeze_readiness=check_freeze_workflow(root, wf, risk)
        except Exception as exc:
            freeze_readiness={'status':'FAIL','errors':[f'could not validate prototype freeze readiness: {exc}']}
    else:
        freeze_readiness={'status':'NOT_PRESENT','message':'prototype freeze not present; frontend_quality_gate does not require it for prototype acceptance'}

    status='PASS' if not findings else 'FAIL'
    return {
        'status': status,
        'scope': 'workflow',
        'risk': risk,
        'workflow': str(wf),
        'score_average': round(avg, 2) if avg is not None else None,
        'score_min': round(min_score, 2) if min_score is not None else None,
        'score_threshold': threshold,
        'score_floor': min_threshold,
        'design_lane_count': lane_count,
        'evidence': ev,
        'evidence_image_counts': {'total': total_images, 'prototype': proto_images, 'production': prod_images, 'visual_or_browser_or_other': visual_images},
        'design_lane_gate': lane_gate_result,
        'reference_aware_critique': reference_aware_result,
        'prototype_freeze_readiness': freeze_readiness,
        'findings': findings,
    }


def main() -> int:
    ap=argparse.ArgumentParser(description='Validate generic high-fidelity frontend prototype gate artifacts and quality thresholds.')
    ap.add_argument('--root', default='.', help='SelfCheck/control-plane root')
    ap.add_argument('--workflow', help='Workflow directory to validate for a concrete frontend task')
    ap.add_argument('--risk', choices=['C','D'], default='C')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    result=check_base(root)
    if args.workflow:
        wf_result=check_workflow(root, Path(args.workflow), args.risk)
        result={'status':'PASS' if result['status']=='PASS' and wf_result['status']=='PASS' else 'FAIL','base':result,'workflow':wf_result}
    if args.format=='json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']}")
        def emit(findings):
            for f in findings:
                print(f"{f['severity']}: {f.get('path','')}: {f['message']}")
        if 'findings' in result: emit(result['findings'])
        else:
            emit(result['base'].get('findings',[])); emit(result['workflow'].get('findings',[]))
    return 0 if result['status']=='PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
