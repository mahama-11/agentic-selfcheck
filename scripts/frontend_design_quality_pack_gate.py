#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

REQUIRED = [
    'PROJECT_CONTEXT.md',
    'REQUIREMENT_ORIGIN_TRACE.md',
    'REFERENCE_PACK.md',
    'AESTHETIC_DIRECTION.md',
    'ANTI_PATTERNS.md',
    'DESIGN_TOKENS_MAP.md',
    'COMPONENT_INVENTORY.md',
    'REFERENCE_SCREENSHOTS.md',
    'PROJECT_FRONTEND_RULES.md',
]
TEMPLATE_DIR='templates/frontend/design-quality-pack'
IMAGE_EXTS={'.png','.jpg','.jpeg','.webp'}


def nonempty(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 80


def finding(sev, path, msg):
    return {'severity': sev, 'path': str(path), 'message': msg}


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''


def count_markdown_table_rows(text: str, min_cols: int = 3) -> int:
    count=0
    for line in text.splitlines():
        if not line.strip().startswith('|'): continue
        if '---' in line or re.search(r'\b(ID|Anti-pattern|Component|Token type|File)\b', line, re.I): continue
        cols=[c.strip() for c in line.strip('|').split('|')]
        if len(cols) >= min_cols and any(c for c in cols):
            nonblank=sum(1 for c in cols if c)
            if nonblank >= min_cols:
                count += 1
    return count


def count_references(wf: Path) -> int:
    text=read(wf/'REFERENCE_PACK.md')
    return count_markdown_table_rows(text, 3)


def count_antipatterns(wf: Path) -> int:
    text=read(wf/'ANTI_PATTERNS.md')
    return count_markdown_table_rows(text, 2) + len([l for l in text.splitlines() if l.strip().startswith('- ') and len(l.strip()) > 3])


def status_value(path: Path, key: str) -> str | None:
    text=read(path)
    m=re.search(rf'{re.escape(key)}\s*:\s*(declared|contract_needed)', text)
    return m.group(1) if m else None


def has_contract_rationale(path: Path) -> bool:
    text=read(path)
    marker='Contract-needed rationale'
    idx=text.find(marker)
    if idx < 0: return False
    tail=text[idx+len(marker):].strip()
    return len(tail) > 20 and 'Fill if' not in tail[:120]


def local_reference_images(wf: Path) -> list[str]:
    found=[]
    for rel in ['reference-screenshots','visual-references','references']:
        d=wf/rel
        if d.exists():
            for p in d.rglob('*'):
                if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                    found.append(str(p))
    return found


def external_reference_waiver(wf: Path) -> bool:
    text=read(wf/'REFERENCE_PACK.md') + '\n' + read(wf/'REFERENCE_SCREENSHOTS.md')
    return 'external_reference_only: true' in text and len(re.findall(r'https?://', text)) >= 2


def check_base(root: Path) -> dict:
    findings=[]
    for name in REQUIRED:
        p=root/TEMPLATE_DIR/name
        if not nonempty(p): findings.append(finding('error', p, 'required design quality pack template missing or empty'))
    schema=root/'schemas/frontend-design-quality-pack.schema.json'
    if not nonempty(schema): findings.append(finding('error', schema, 'schema missing or empty'))
    return {'status':'PASS' if not findings else 'FAIL','scope':'base','findings':findings}


def check_workflow(root: Path, workflow: Path, risk: str) -> dict:
    wf=workflow if workflow.is_absolute() else root/workflow
    risk=risk.upper()
    findings=[]
    if not wf.exists():
        return {'status':'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'findings':[finding('error', wf, 'workflow does not exist')]}
    for name in REQUIRED:
        p=wf/name
        if not nonempty(p): findings.append(finding('error', p, f'required design quality artifact missing or empty for risk {risk}'))
    refs=count_references(wf)
    ref_min=3 if risk=='D' else 2
    if refs < ref_min:
        findings.append(finding('error', wf/'REFERENCE_PACK.md', f'{risk}-risk requires at least {ref_min} reference entries; found {refs}'))
    anti=count_antipatterns(wf)
    anti_min=3 if risk=='D' else 1
    if anti < anti_min:
        findings.append(finding('error', wf/'ANTI_PATTERNS.md', f'{risk}-risk requires at least {anti_min} anti-patterns; found {anti}'))
    t=status_value(wf/'DESIGN_TOKENS_MAP.md','tokens_status')
    if t not in {'declared','contract_needed'}:
        findings.append(finding('error', wf/'DESIGN_TOKENS_MAP.md', 'tokens_status must be declared or contract_needed'))
    elif t=='contract_needed' and not has_contract_rationale(wf/'DESIGN_TOKENS_MAP.md'):
        findings.append(finding('error', wf/'DESIGN_TOKENS_MAP.md', 'tokens_status contract_needed requires rationale'))
    c=status_value(wf/'COMPONENT_INVENTORY.md','components_status')
    if c not in {'declared','contract_needed'}:
        findings.append(finding('error', wf/'COMPONENT_INVENTORY.md', 'components_status must be declared or contract_needed'))
    elif c=='contract_needed' and not has_contract_rationale(wf/'COMPONENT_INVENTORY.md'):
        findings.append(finding('error', wf/'COMPONENT_INVENTORY.md', 'components_status contract_needed requires rationale'))
    imgs=local_reference_images(wf)
    waiver=external_reference_waiver(wf)
    if risk=='D' and len(imgs) < 2 and not waiver:
        findings.append(finding('error', wf/'reference-screenshots', 'D-risk requires at least 2 local reference images or external_reference_only waiver with >=2 URLs'))
    rules=read(wf/'PROJECT_FRONTEND_RULES.md')
    context=read(wf/'PROJECT_CONTEXT.md')
    required_context_markers=[
        'Existing product background',
        'Current implementation state',
        'Current visual and interaction baseline',
        'Prototype maturity goal and assessment',
        'Target increment goal',
        'Business logic and interaction backbone',
        'System feasibility map',
        'User-facing product UI boundary',
        'Prototype grounding rule',
    ]
    for marker in required_context_markers:
        if marker not in context:
            findings.append(finding('error', wf/'PROJECT_CONTEXT.md', f'project context must include section: {marker}'))
    if re.search(r'(Fill if|Product purpose:\s*$|Existing routes/pages affected:\s*$|Theme / color / typography / spacing direction:\s*$|New user job:\s*$)', context, re.M):
        findings.append(finding('error', wf/'PROJECT_CONTEXT.md', 'project context contains unfilled placeholders'))
    if risk=='D':
        backbone_terms=['Core business objects involved', 'End-to-end user flow', 'Step-by-step interaction model', 'Critical states']
        for term in backbone_terms:
            if term not in context:
                findings.append(finding('error', wf/'PROJECT_CONTEXT.md', f'D-risk requires business backbone field: {term}'))
        feasibility_terms=['Existing frontend route/component/state support', 'Existing backend/API/data support', 'contract-needed']
        for term in feasibility_terms:
            if term not in context:
                findings.append(finding('error', wf/'PROJECT_CONTEXT.md', f'D-risk requires feasibility mapping field: {term}'))
        boundary_terms=['Forbidden in user-facing prototype UI', 'Translate internal state into user language']
        for term in boundary_terms:
            if term not in context:
                findings.append(finding('error', wf/'PROJECT_CONTEXT.md', f'D-risk requires user-facing UI boundary field: {term}'))
    goal=re.search(r'prototype_maturity_goal\s*:\s*(stage_[1-4])', context)
    current=re.search(r'current_maturity_assessment\s*:\s*(stage_[1-4])', context)
    if not goal:
        findings.append(finding('error', wf/'PROJECT_CONTEXT.md', 'prototype_maturity_goal must be declared as stage_1..stage_4'))
    elif risk=='D' and goal.group(1) != 'stage_4':
        findings.append(finding('error', wf/'PROJECT_CONTEXT.md', 'D-risk prototype maturity goal should be stage_4; ladder is diagnostic, not staged delivery'))
    if not current:
        findings.append(finding('error', wf/'PROJECT_CONTEXT.md', 'current_maturity_assessment must be declared as stage_1..stage_4'))
    if risk=='D' and 'human_review_boundary' not in rules:
        findings.append(finding('error', wf/'PROJECT_FRONTEND_RULES.md', 'D-risk requires human_review_boundary declaration'))
    trace=read(wf/'REQUIREMENT_ORIGIN_TRACE.md')
    trace_markers=['Source-of-truth documents','Requirement sections / anchors','Multi-surface target map','Loss prevention rule','Coverage delta log']
    for marker in trace_markers:
        if marker not in trace:
            findings.append(finding('error', wf/'REQUIREMENT_ORIGIN_TRACE.md', f'requirement trace must include section: {marker}'))
    if re.search(r'(Fill source|Fill path|Fill section|Fill requirement|Fill user job|Fill skeleton|Fill previous|pending\s*\|?\s*$)', trace, re.M):
        findings.append(finding('error', wf/'REQUIREMENT_ORIGIN_TRACE.md', 'requirement trace contains unfilled placeholders'))
    anchor_rows=count_markdown_table_rows(trace, 5)
    min_anchor_rows=5 if risk=='D' else 3
    if anchor_rows < min_anchor_rows:
        findings.append(finding('error', wf/'REQUIREMENT_ORIGIN_TRACE.md', f'{risk}-risk requires at least {min_anchor_rows} traced requirement/surface/delta rows; found {anchor_rows}'))
    if risk=='D' and not re.search(r'(do not regress|must not regress|不回退|不得回退|不能丢)', trace, re.I):
        findings.append(finding('error', wf/'REQUIREMENT_ORIGIN_TRACE.md', 'D-risk requires explicit non-regression rule for previously good prototype parts'))
    return {'status':'PASS' if not findings else 'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'reference_count':refs,'anti_pattern_count':anti,'reference_images':imgs,'external_reference_waiver':waiver,'findings':findings}


def main() -> int:
    ap=argparse.ArgumentParser(description='Validate frontend design quality pack artifacts before AI prototype generation.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--workflow')
    ap.add_argument('--risk', choices=['C','D'], default='C')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    result=check_base(root)
    if args.workflow:
        wf=check_workflow(root, Path(args.workflow), args.risk)
        result={'status':'PASS' if result['status']=='PASS' and wf['status']=='PASS' else 'FAIL','base':result,'workflow':wf}
    if args.format=='json': print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']}")
        fs=result.get('findings') or result.get('base',{}).get('findings',[])+result.get('workflow',{}).get('findings',[])
        for f in fs: print(f"{f['severity']}: {f['path']}: {f['message']}")
    return 0 if result['status']=='PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
