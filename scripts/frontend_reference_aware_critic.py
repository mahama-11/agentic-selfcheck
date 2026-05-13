#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

PASS_VERDICTS = {'PASS', 'PASS_WITH_NOTES'}
DQP_FILES = ['REFERENCE_PACK.md','AESTHETIC_DIRECTION.md','ANTI_PATTERNS.md','DESIGN_TOKENS_MAP.md','COMPONENT_INVENTORY.md','PROJECT_FRONTEND_RULES.md']
PACK_KEYS = {
    'reference_pack': 'REFERENCE_PACK.md',
    'aesthetic_direction': 'AESTHETIC_DIRECTION.md',
    'anti_patterns': 'ANTI_PATTERNS.md',
    'design_tokens_map': 'DESIGN_TOKENS_MAP.md',
    'component_inventory': 'COMPONENT_INVENTORY.md',
    'project_frontend_rules': 'PROJECT_FRONTEND_RULES.md',
}


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def json_schema_errors(root: Path) -> list[str]:
    schema = root / 'schemas/frontend-reference-aware-critique.schema.json'
    if not schema.exists() or schema.stat().st_size < 100:
        return ['schema missing or empty']
    try:
        json.loads(schema.read_text(encoding='utf-8'))
    except Exception as exc:
        return [f'schema invalid JSON: {exc}']
    return []


def prompt_text(wf: Path, risk: str) -> str:
    pack = []
    for name in DQP_FILES:
        pack.append(f"## {name}\n{read(wf / name)[:4000]}")
    vc = read(wf / 'visual-critique.json')[:5000]
    return f"""You are an independent senior frontend design critic. You are not only grading screenshots; you must judge the prototype against the upstream Design Quality Pack.

Workflow: {wf}
Risk: {risk}

Return ONLY JSON matching schemas/frontend-reference-aware-critique.schema.json.

Hard rules:
- If references_used is below risk threshold, verdict must be REQUEST_CHANGES.
- If anti_pattern_check.violations is non-empty, verdict must not be PASS.
- If token/component fit is misaligned, verdict must not be PASS.
- C threshold: average context score >= 3.8, no dimension below 3.0, references_used >= 2.
- D threshold: average context score >= 4.2, no dimension below 3.5, references_used >= 3.

Use the existing visual critique as input, but override it if it conflicts with the Design Quality Pack.

# Existing visual critique
{vc}

# Design Quality Pack
{chr(10).join(pack)}
"""


def validate_payload(root: Path, wf: Path, risk: str, data: dict) -> list[str]:
    errors: list[str] = []
    errors.extend(json_schema_errors(root))
    if not isinstance(data, dict):
        return errors + ['payload must be a JSON object']
    allowed_top = {'schema_version','risk','workflow','critique_source','design_quality_pack','reference_alignment','aesthetic_alignment','anti_pattern_check','token_component_fit','project_rules_alignment','verdict','required_changes','average_context_score'}
    extra = set(data) - allowed_top
    if extra:
        errors.append('unexpected top-level fields: ' + ', '.join(sorted(extra)))
    required = ['schema_version','risk','workflow','critique_source','design_quality_pack','reference_alignment','aesthetic_alignment','anti_pattern_check','token_component_fit','project_rules_alignment','verdict','required_changes']
    for key in required:
        if key not in data:
            errors.append(f'missing required field: {key}')
    if errors:
        return errors
    for obj_key in ['design_quality_pack','reference_alignment','aesthetic_alignment','anti_pattern_check','token_component_fit','project_rules_alignment']:
        if not isinstance(data.get(obj_key), dict):
            errors.append(f'{obj_key} must be an object')
    nested_allowed={
        'design_quality_pack': set(PACK_KEYS.keys()),
        'reference_alignment': {'references_used','borrowed_principles','not_copied_elements','score'},
        'aesthetic_alignment': {'score','matches','gaps'},
        'anti_pattern_check': {'violations','avoided','score'},
        'token_component_fit': {'status','score','notes'},
        'project_rules_alignment': {'score','matched_rules','violated_rules'},
    }
    nested_required={
        'design_quality_pack': set(PACK_KEYS.keys()),
        'reference_alignment': {'references_used','borrowed_principles','not_copied_elements','score'},
        'aesthetic_alignment': {'score','matches','gaps'},
        'anti_pattern_check': {'violations','avoided','score'},
        'token_component_fit': {'status','score','notes'},
        'project_rules_alignment': {'score','matched_rules','violated_rules'},
    }
    for obj_key, allowed in nested_allowed.items():
        obj=data.get(obj_key) if isinstance(data.get(obj_key), dict) else {}
        extra=set(obj) - allowed
        missing=nested_required[obj_key] - set(obj)
        if extra:
            errors.append(f'{obj_key} has unexpected fields: ' + ', '.join(sorted(extra)))
        if missing:
            errors.append(f'{obj_key} missing fields: ' + ', '.join(sorted(missing)))
    if not isinstance(data.get('required_changes'), list) or not all(isinstance(x, str) for x in data.get('required_changes', [])):
        errors.append('required_changes must be an array of strings')
    if errors:
        return errors
    if data.get('schema_version') != '1.0':
        errors.append('schema_version must be 1.0')
    if data.get('risk') != risk:
        errors.append(f'risk must match CLI risk {risk}')
    if str(data.get('workflow','')).strip() not in {str(wf), wf.name}:
        errors.append('workflow must match the validated workflow path or name')
    if str(data.get('critique_source','')).strip() not in {'visual-critique.json', str(wf/'visual-critique.json')}:
        errors.append('critique_source must be visual-critique.json for this workflow')
    if data.get('verdict') not in {'PASS','PASS_WITH_NOTES','REQUEST_CHANGES','REJECT_DIRECTION'}:
        errors.append('invalid verdict')

    try:
        from frontend_design_quality_pack_gate import check_workflow as check_dqp
        dqp = check_dqp(root, wf, risk)
        if dqp.get('status') != 'PASS':
            errors.append('Design Quality Pack gate must PASS before reference-aware critique')
    except Exception as exc:
        errors.append(f'could not run Design Quality Pack gate: {exc}')

    vc_path = wf / 'visual-critique.json'
    if not vc_path.exists():
        errors.append('visual-critique.json missing')
    else:
        try:
            vc = load_json(vc_path)
            if vc.get('verdict') not in PASS_VERDICTS:
                errors.append('source visual-critique verdict is not passable')
        except Exception as exc:
            errors.append(f'visual-critique.json invalid JSON: {exc}')

    dqp_obj = data.get('design_quality_pack') or {}
    for key, fname in PACK_KEYS.items():
        val = str(dqp_obj.get(key, '')).strip()
        if not val:
            errors.append(f'design_quality_pack.{key} missing')
        if val and fname not in val:
            errors.append(f'design_quality_pack.{key} should point to {fname}')

    refs = (data.get('reference_alignment') or {}).get('references_used')
    if not isinstance(refs, list) or not all(isinstance(x, str) and x.strip() for x in refs):
        errors.append('reference_alignment.references_used must be a non-empty array of strings')
        refs=[]
    ref_min = 3 if risk == 'D' else 2
    if len(refs) < ref_min:
        errors.append(f'{risk}-risk requires at least {ref_min} references_used; found {len(refs)}')

    scores = []
    for object_key in ['reference_alignment','aesthetic_alignment','anti_pattern_check','token_component_fit','project_rules_alignment']:
        raw=(data.get(object_key) or {}).get('score')
        if not isinstance(raw, (int, float)) or isinstance(raw, bool):
            errors.append(f'{object_key}.score must be a JSON number')
            continue
        value = float(raw)
        if not 1 <= value <= 5:
            errors.append(f'{object_key}.score out of range')
        scores.append(value)
    avg = sum(scores) / len(scores) if len(scores) == 5 else None
    mn = min(scores) if len(scores) == 5 else None
    threshold = 4.2 if risk == 'D' else 3.8
    floor = 3.5 if risk == 'D' else 3.0
    if avg is not None and avg < threshold:
        errors.append(f'average context score {avg:.2f} below {risk} threshold {threshold:.1f}')
    if mn is not None and mn < floor:
        errors.append(f'min context dimension {mn:.1f} below {risk} floor {floor:.1f}')

    if (data.get('anti_pattern_check') or {}).get('violations'):
        errors.append('anti_pattern_check.violations must be empty for passable critique')
    for list_path in [('reference_alignment','borrowed_principles'),('reference_alignment','not_copied_elements'),('aesthetic_alignment','matches'),('aesthetic_alignment','gaps'),('anti_pattern_check','violations'),('anti_pattern_check','avoided'),('token_component_fit','notes'),('project_rules_alignment','matched_rules'),('project_rules_alignment','violated_rules')]:
        value=(data.get(list_path[0]) or {}).get(list_path[1])
        if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
            errors.append(f'{list_path[0]}.{list_path[1]} must be an array of strings')
    if (data.get('token_component_fit') or {}).get('status') not in {'aligned','contract_needed','misaligned'}:
        errors.append('token_component_fit.status must be aligned, contract_needed, or misaligned')
    if (data.get('token_component_fit') or {}).get('status') == 'misaligned':
        errors.append('token_component_fit.status misaligned is not passable')
    if (data.get('project_rules_alignment') or {}).get('violated_rules'):
        errors.append('project_rules_alignment.violated_rules must be empty for passable critique')
    if data.get('verdict') not in PASS_VERDICTS:
        errors.append('verdict is not passable')
    if data.get('required_changes') and data.get('verdict') == 'PASS':
        errors.append('PASS verdict cannot have required_changes')
    return errors


def render_markdown(data: dict) -> str:
    dims = [
        ('Reference alignment', data['reference_alignment']['score']),
        ('Aesthetic direction alignment', data['aesthetic_alignment']['score']),
        ('Anti-pattern avoidance', data['anti_pattern_check']['score']),
        ('Token/component fit', data['token_component_fit']['score']),
        ('Project rules alignment', data['project_rules_alignment']['score']),
    ]
    avg = sum(float(score) for _, score in dims) / len(dims)
    rows = '\n'.join([f'| {name} | {float(score):.1f} |' for name, score in dims])
    refs = '\n'.join([f'- {x}' for x in data['reference_alignment'].get('references_used', [])]) or '- None'
    violations = '\n'.join([f'- {x}' for x in data['anti_pattern_check'].get('violations', [])]) or '- None'
    changes = '\n'.join([f'- {x}' for x in data.get('required_changes', [])]) or '- None'
    notes = '; '.join(data['token_component_fit'].get('notes', []))
    matched = '; '.join(data['project_rules_alignment'].get('matched_rules', []))
    violated = '; '.join(data['project_rules_alignment'].get('violated_rules', [])) or 'None'
    return f"""# Reference-Aware Visual Critique

## Verdict

{data['verdict']}

## Context scorecard

| Dimension | Score |
|---|---:|
{rows}

Average context score: {avg:.2f}

## References used

{refs}

## Anti-pattern violations

{violations}

## Token/component fit

- status: {data['token_component_fit']['status']}
- notes: {notes}

## Project rule alignment

- matched: {matched}
- violated: {violated}

## Required changes

{changes}
"""


def main() -> int:
    ap = argparse.ArgumentParser(description='Validate/materialize reference-aware visual critique against Design Quality Pack.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--workflow', required=True)
    ap.add_argument('--risk', choices=['C','D'], required=True)
    ap.add_argument('--input-json')
    ap.add_argument('--write-artifacts', action='store_true')
    ap.add_argument('--print-prompt', action='store_true')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    wf = Path(args.workflow)
    wf = wf if wf.is_absolute() else root / wf
    if args.print_prompt:
        print(prompt_text(wf, args.risk))
        return 0
    if not args.input_json:
        raise SystemExit('--input-json required unless --print-prompt')
    try:
        data = load_json(Path(args.input_json))
    except Exception as exc:
        result = {'status': 'FAIL', 'errors': [f'input JSON cannot be loaded: {exc}'], 'input': str(args.input_json), 'workflow': str(wf)}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == 'json' else 'status=FAIL\n' + '\n'.join(result['errors']))
        return 1
    errors = validate_payload(root, wf, args.risk, data)
    result = {'status': 'PASS' if not errors else 'FAIL', 'errors': errors, 'input': str(args.input_json), 'workflow': str(wf)}
    if args.write_artifacts and not errors:
        (wf / 'REFERENCE_AWARE_CRITIQUE.md').write_text(render_markdown(data), encoding='utf-8')
        (wf / 'reference-aware-critique.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        result['written'] = ['REFERENCE_AWARE_CRITIQUE.md', 'reference-aware-critique.json']
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.format == 'json' else 'status=' + result['status'] + '\n' + '\n'.join(errors))
    return 0 if not errors else 1

if __name__ == '__main__':
    raise SystemExit(main())
