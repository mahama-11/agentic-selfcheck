#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, zlib
from pathlib import Path
from typing import Any

TEMPLATE_DIR = Path('templates/frontend/prototype-freeze')
REQUIRED_TEMPLATES = ['PROTOTYPE_FREEZE.md','COMPONENT_MAPPING.md','API_STATE_MAPPING.md','IMPLEMENTATION_CONTRACT.md']
REQUIRED_ACCEPTANCE = ['PROTOTYPE_ACCEPTANCE.md','visual-critique.json','reference-aware-critique.json']
PASS_VERDICTS = {'PASS','PASS_WITH_NOTES'}
ACCEPTANCE_TERMS = {'ACCEPTED','ACCEPTED_WITH_NOTES'}
ALLOWED_TOP = {'schema_version','risk','workflow','selected_lane','accepted_prototype','frozen_screenshots','component_mapping','api_state_mapping','implementation_contract','deviations','approval'}


def finding(sev: str, path: Any, msg: str) -> dict:
    return {'severity': sev, 'path': str(path), 'message': msg}


def nonempty(p: Path, min_size: int = 40) -> bool:
    try:
        return p.exists() and p.is_file() and p.stat().st_size >= min_size
    except OSError:
        return False


def read(p: Path) -> str:
    return p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''


def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding='utf-8'))


def is_valid_png_data(data: bytes) -> bool:
    sig=b'\x89PNG\r\n\x1a\n'
    if len(data) < 57 or not data.startswith(sig):
        return False
    pos=len(sig); seen_ihdr=False; seen_idat=False; seen_iend=False
    width=height=bit_depth=color_type=None
    idat=[]
    try:
        while pos + 12 <= len(data):
            length=int.from_bytes(data[pos:pos+4], 'big'); pos += 4
            ctype=data[pos:pos+4]; pos += 4
            if pos + length + 4 > len(data): return False
            chunk=data[pos:pos+length]; pos += length
            crc_expected=int.from_bytes(data[pos:pos+4], 'big'); pos += 4
            if (zlib.crc32(ctype + chunk) & 0xffffffff) != crc_expected: return False
            if not seen_ihdr:
                if ctype != b'IHDR' or length != 13: return False
                width=int.from_bytes(chunk[0:4], 'big'); height=int.from_bytes(chunk[4:8], 'big')
                bit_depth=chunk[8]; color_type=chunk[9]
                valid_depths={0:{1,2,4,8,16},2:{8,16},3:{1,2,4,8},4:{8,16},6:{8,16}}
                if width <= 0 or height <= 0 or color_type not in valid_depths or bit_depth not in valid_depths[color_type]: return False
                if chunk[10] != 0 or chunk[11] != 0 or chunk[12] != 0: return False
                seen_ihdr=True
            elif ctype == b'IHDR':
                return False
            if ctype == b'IDAT':
                seen_idat=True; idat.append(chunk)
            if ctype == b'IEND':
                seen_iend=True; break
        if not (seen_ihdr and seen_idat and seen_iend and pos == len(data)): return False
        raw=zlib.decompress(b''.join(idat))
        channels={0:1,2:3,3:1,4:2,6:4}[color_type]
        scanline=1 + ((width * channels * bit_depth + 7)//8)
        if len(raw) != scanline * height: return False
        return all(raw[row*scanline] in {0,1,2,3,4} for row in range(height))
    except Exception:
        return False


def is_valid_png(p: Path) -> bool:
    try:
        return p.suffix.lower() == '.png' and p.is_file() and p.stat().st_size > 0 and is_valid_png_data(p.read_bytes())
    except OSError:
        return False


def is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def resolve_existing(root: Path, wf: Path, raw: str, allowed_bases: list[Path] | None = None, must_be_file: bool | None = None) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    p=Path(raw.strip())
    candidates=[]
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.extend([wf/p, root/p])
    bases=[b.resolve() for b in (allowed_bases or [wf, root])]
    for c in candidates:
        try:
            resolved=c.resolve()
        except OSError:
            continue
        if not any(is_within(resolved, b) for b in bases):
            continue
        if not resolved.exists():
            continue
        if must_be_file is True and not resolved.is_file():
            continue
        if must_be_file is False and not resolved.is_dir():
            continue
        return resolved
    return None


def resolve_lane(root: Path, wf: Path, selected: str) -> Path | None:
    if not selected or not isinstance(selected, str): return None
    p=Path(selected)
    if p.is_absolute() or len(p.parts) > 1:
        lane=resolve_existing(root, wf, selected, [wf, root], must_be_file=False)
        if lane and (is_within(lane, wf/'design-lanes') or is_within(lane, wf) or is_within(lane, root)):
            return lane
        return None
    d=wf/'design-lanes'/selected
    return d.resolve() if d.exists() and d.is_dir() and is_within(d.resolve(), wf/'design-lanes') else None


def resolve_screenshot(root: Path, wf: Path, raw: str) -> Path | None:
    return resolve_existing(root, wf, raw, [wf/'prototype-screenshots', wf/'frozen-prototype'], must_be_file=True)


def listed_screenshots(root: Path, wf: Path, data: dict) -> tuple[list[Path], list[str]]:
    out=[]; errors=[]
    items=data.get('frozen_screenshots')
    if not isinstance(items, list):
        return out, ['frozen_screenshots must be an array']
    if not items:
        return out, ['frozen_screenshots must list at least one screenshot; discovery fallback is not allowed']
    for i,item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f'frozen_screenshots[{i}] must be an object')
            continue
        raw=item.get('path')
        p=resolve_screenshot(root, wf, raw) if raw else None
        if p:
            out.append(p)
        else:
            errors.append(f'frozen_screenshots[{i}].path must resolve to an existing file under prototype-screenshots/ or frozen-prototype/')
    return out, errors


def discovered_screenshots(wf: Path) -> list[Path]:
    d=wf/'prototype-screenshots'
    return sorted([p for p in d.rglob('*.png') if p.is_file()]) if d.exists() else []


def schema_errors(root: Path) -> list[str]:
    p=root/'schemas/frontend-prototype-freeze.schema.json'
    if not nonempty(p, 100): return ['prototype-freeze schema missing or empty']
    try:
        json.loads(p.read_text(encoding='utf-8'))
    except Exception as exc:
        return [f'prototype-freeze schema invalid JSON: {exc}']
    return []


def check_base(root: Path) -> dict:
    findings=[]
    for name in REQUIRED_TEMPLATES:
        p=root/TEMPLATE_DIR/name
        if not nonempty(p, 80): findings.append(finding('error', p, 'required prototype-freeze template missing or empty'))
    for err in schema_errors(root): findings.append(finding('error', root/'schemas/frontend-prototype-freeze.schema.json', err))
    return {'status':'PASS' if not findings else 'FAIL','scope':'base','findings':findings}


def structural_errors(data: Any) -> list[str]:
    errors=[]
    if not isinstance(data, dict): return ['payload must be a JSON object']
    extra=set(data) - ALLOWED_TOP
    if extra: errors.append('unexpected top-level fields: ' + ', '.join(sorted(extra)))
    required=ALLOWED_TOP
    missing=required - set(data)
    if missing: errors.append('missing required fields: ' + ', '.join(sorted(missing)))
    nested_allowed={
        'accepted_prototype': {'artifact_path','acceptance_doc','notes'},
        'implementation_contract': {'owner','readiness','scope','handoff_artifacts','open_questions'},
        'approval': {'owner','status','rationale','date','approved_at'},
    }
    nested_required={
        'accepted_prototype': {'artifact_path','acceptance_doc'},
        'implementation_contract': {'owner','readiness','scope','handoff_artifacts','open_questions'},
        'approval': {'owner','status','rationale'},
    }
    for key, allowed in nested_allowed.items():
        obj=data.get(key)
        if not isinstance(obj, dict): errors.append(f'{key} must be an object'); continue
        extra=set(obj)-allowed
        if extra: errors.append(f'{key} has unexpected fields: ' + ', '.join(sorted(extra)))
        missing=nested_required.get(key,set())-set(obj)
        if missing: errors.append(f'{key} missing required fields: ' + ', '.join(sorted(missing)))
    approval=data.get('approval') if isinstance(data.get('approval'), dict) else {}
    if isinstance(approval, dict) and not (str(approval.get('date','')).strip() or str(approval.get('approved_at','')).strip()):
        errors.append('approval requires date or approved_at')
    for key in ['frozen_screenshots','component_mapping','api_state_mapping','deviations']:
        if not isinstance(data.get(key), list): errors.append(f'{key} must be an array')
    if isinstance(data.get('frozen_screenshots'), list):
        if not data['frozen_screenshots']:
            errors.append('frozen_screenshots must include at least one item')
        for i,item in enumerate(data['frozen_screenshots']):
            if not isinstance(item, dict):
                errors.append(f'frozen_screenshots[{i}] must be an object')
                continue
            extra=set(item)-{'screen','path'}
            if extra: errors.append(f'frozen_screenshots[{i}] has unexpected fields: ' + ', '.join(sorted(extra)))
            missing={'screen','path'}-set(item)
            if missing: errors.append(f'frozen_screenshots[{i}] missing required fields: ' + ', '.join(sorted(missing)))
    return errors


def has_nonempty_string(obj: dict, key: str) -> bool:
    return isinstance(obj.get(key), str) and bool(obj.get(key, '').strip())


def check_workflow(root: Path, workflow: Path, risk: str, input_json: Path | None = None) -> dict:
    wf=workflow if workflow.is_absolute() else root/workflow
    risk=risk.upper(); findings=[]
    if not wf.exists():
        return {'status':'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'findings':[finding('error', wf, 'workflow does not exist')]}
    payload_path=input_json if input_json and input_json.is_absolute() else (root/input_json if input_json else wf/'prototype-freeze.json')
    data=None
    if not payload_path.exists():
        findings.append(finding('error', payload_path, 'prototype-freeze payload missing'))
    else:
        try: data=load_json(payload_path)
        except Exception as exc: findings.append(finding('error', payload_path, f'prototype-freeze payload invalid JSON: {exc}'))
    for name in REQUIRED_ACCEPTANCE:
        p=wf/name
        if not nonempty(p): findings.append(finding('error', p, 'required previous prototype acceptance artifact missing or empty'))
    if nonempty(wf/'PROTOTYPE_ACCEPTANCE.md'):
        txt=read(wf/'PROTOTYPE_ACCEPTANCE.md').upper()
        if not any(term in txt for term in ACCEPTANCE_TERMS): findings.append(finding('error', wf/'PROTOTYPE_ACCEPTANCE.md', 'prototype acceptance must be ACCEPTED or ACCEPTED_WITH_NOTES'))
    for critique in ['visual-critique.json','reference-aware-critique.json']:
        p=wf/critique
        if nonempty(p):
            try:
                obj=load_json(p); verdict=obj.get('verdict')
                if verdict and verdict not in PASS_VERDICTS: findings.append(finding('error', p, f'{critique} verdict is not passable'))
            except Exception as exc: findings.append(finding('error', p, f'{critique} invalid JSON: {exc}'))
    if data is None:
        return {'status':'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'payload':str(payload_path),'findings':findings}
    for err in structural_errors(data): findings.append(finding('error', payload_path, err))
    if data.get('schema_version') != '1.0': findings.append(finding('error', payload_path, 'schema_version must be 1.0'))
    if data.get('risk') != risk: findings.append(finding('error', payload_path, f'risk must match CLI risk {risk}'))
    if str(data.get('workflow','')).strip() not in {str(wf), wf.name}: findings.append(finding('error', payload_path, 'workflow must match workflow path or name'))
    lane=resolve_lane(root, wf, data.get('selected_lane',''))
    if not lane: findings.append(finding('error', payload_path, 'selected_lane must be non-empty and resolve to an existing lane directory/path under the workflow or repo root'))
    accepted=data.get('accepted_prototype') if isinstance(data.get('accepted_prototype'), dict) else {}
    artifact=resolve_existing(root, wf, accepted.get('artifact_path',''), [wf, root], must_be_file=True) if accepted else None
    if not artifact: findings.append(finding('error', payload_path, 'accepted_prototype.artifact_path must resolve to an existing file under the workflow or repo root'))
    acc_doc=resolve_existing(root, wf, accepted.get('acceptance_doc',''), [wf, root], must_be_file=True) if accepted else None
    if not acc_doc: findings.append(finding('error', payload_path, 'accepted_prototype.acceptance_doc must resolve to an existing file under the workflow or repo root'))
    shots, shot_errors=listed_screenshots(root, wf, data)
    for err in shot_errors: findings.append(finding('error', payload_path, err))
    valid_shots=[p for p in shots if is_valid_png(p)]
    invalid_shots=[p for p in shots if not is_valid_png(p)]
    if not valid_shots: findings.append(finding('error', wf/'prototype-screenshots', 'at least one listed frozen screenshot must be a strict valid PNG'))
    for p in invalid_shots: findings.append(finding('error', p, 'frozen screenshot is missing or not a strict valid PNG'))
    cm=data.get('component_mapping') if isinstance(data.get('component_mapping'), list) else []
    if not cm: findings.append(finding('error', payload_path, 'component_mapping must include at least one entry'))
    for i,e in enumerate(cm):
        path=f'component_mapping[{i}]'
        if not isinstance(e, dict): findings.append(finding('error', payload_path, f'{path} must be an object')); continue
        extra=set(e)-{'prototype_element','production_component','status','rationale'}
        if extra: findings.append(finding('error', payload_path, f'{path} has unexpected fields: ' + ', '.join(sorted(extra))))
        if not has_nonempty_string(e, 'prototype_element'): findings.append(finding('error', payload_path, f'{path}.prototype_element is required'))
        if 'status' not in e or not has_nonempty_string(e, 'status'):
            findings.append(finding('error', payload_path, f'{path}.status is required'))
            status=None
        else:
            status=e.get('status')
        if status is not None and status not in {'mapped','contract_needed'}: findings.append(finding('error', payload_path, f'{path}.status must be mapped or contract_needed'))
        if status == 'contract_needed':
            if not has_nonempty_string(e, 'rationale'): findings.append(finding('error', payload_path, f'{path} contract_needed requires rationale'))
        elif status == 'mapped' and not has_nonempty_string(e, 'production_component'):
            findings.append(finding('error', payload_path, f'{path}.production_component is required unless contract_needed'))
    am=data.get('api_state_mapping') if isinstance(data.get('api_state_mapping'), list) else []
    if not am: findings.append(finding('error', payload_path, 'api_state_mapping must include at least one entry'))
    for i,e in enumerate(am):
        path=f'api_state_mapping[{i}]'
        if not isinstance(e, dict): findings.append(finding('error', payload_path, f'{path} must be an object')); continue
        extra=set(e)-{'prototype_state','production_source','status','rationale'}
        if extra: findings.append(finding('error', payload_path, f'{path} has unexpected fields: ' + ', '.join(sorted(extra))))
        if not has_nonempty_string(e, 'prototype_state'): findings.append(finding('error', payload_path, f'{path}.prototype_state is required'))
        if 'status' not in e or not has_nonempty_string(e, 'status'):
            findings.append(finding('error', payload_path, f'{path}.status is required'))
            status=None
        else:
            status=e.get('status')
        if status is not None and status not in {'mapped','contract_needed'}: findings.append(finding('error', payload_path, f'{path}.status must be mapped or contract_needed'))
        if status == 'contract_needed':
            if not has_nonempty_string(e, 'rationale'): findings.append(finding('error', payload_path, f'{path} contract_needed requires rationale'))
        elif status == 'mapped' and not has_nonempty_string(e, 'production_source'):
            findings.append(finding('error', payload_path, f'{path}.production_source is required unless contract_needed'))
    impl=data.get('implementation_contract') if isinstance(data.get('implementation_contract'), dict) else {}
    for key in ['owner','readiness','scope']:
        if not str(impl.get(key,'')).strip(): findings.append(finding('error', payload_path, f'implementation_contract.{key} is required'))
    for key in ['handoff_artifacts','open_questions']:
        if not isinstance(impl.get(key), list): findings.append(finding('error', payload_path, f'implementation_contract.{key} must be an array'))
    deviations=data.get('deviations') if isinstance(data.get('deviations'), list) else []
    for i,d in enumerate(deviations):
        path=f'deviations[{i}]'
        if not isinstance(d, dict): findings.append(finding('error', payload_path, f'{path} must be an object')); continue
        extra=set(d)-{'description','material','approval_status','rationale'}
        if extra: findings.append(finding('error', payload_path, f'{path} has unexpected fields: ' + ', '.join(sorted(extra))))
        missing={'description','material','approval_status','rationale'}-set(d)
        if missing: findings.append(finding('error', payload_path, f'{path} missing required fields: ' + ', '.join(sorted(missing))))
        if 'description' in d and not has_nonempty_string(d, 'description'):
            findings.append(finding('error', payload_path, f'{path}.description is required'))
        if 'material' in d and not isinstance(d.get('material'), bool):
            findings.append(finding('error', payload_path, f'{path}.material must be a boolean'))
        if 'approval_status' in d:
            if not has_nonempty_string(d, 'approval_status'):
                findings.append(finding('error', payload_path, f'{path}.approval_status is required'))
            elif d.get('approval_status') not in {'none','pending','approved'}:
                findings.append(finding('error', payload_path, f'{path}.approval_status must be one of none, pending, approved'))
        if 'rationale' in d and not has_nonempty_string(d, 'rationale'):
            findings.append(finding('error', payload_path, f'{path}.rationale is required'))
        if d.get('material') is True and (d.get('approval_status') != 'approved' or not has_nonempty_string(d, 'rationale')):
            findings.append(finding('error', payload_path, f'{path} material deviation requires approval_status approved and rationale'))
    approval=data.get('approval') if isinstance(data.get('approval'), dict) else {}
    if not str(approval.get('owner','')).strip(): findings.append(finding('error', payload_path, 'approval.owner is required'))
    if not str(approval.get('rationale','')).strip(): findings.append(finding('error', payload_path, 'approval.rationale is required'))
    if not (str(approval.get('date','')).strip() or str(approval.get('approved_at','')).strip()): findings.append(finding('error', payload_path, 'approval.date or approval.approved_at is required'))
    status=approval.get('status')
    allowed={'human_approved'} if risk == 'D' else {'accepted','human_approved'}
    if status not in allowed: findings.append(finding('error', payload_path, f'approval.status must be one of {sorted(allowed)} for {risk}-risk'))
    return {'status':'PASS' if not findings else 'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'payload':str(payload_path),'selected_lane_path':str(lane) if lane else None,'frozen_screenshots':[str(p) for p in valid_shots],'findings':findings}


def init_artifacts(root: Path, workflow: Path, force: bool=False) -> list[str]:
    wf=workflow if workflow.is_absolute() else root/workflow
    wf.mkdir(parents=True, exist_ok=True)
    out=[]
    tmpl=root/TEMPLATE_DIR
    for name in REQUIRED_TEMPLATES:
        target=wf/name
        if target.exists() and not force: continue
        shutil.copyfile(tmpl/name, target); out.append(str(target))
    (wf/'frozen-prototype').mkdir(exist_ok=True)
    return out


def main() -> int:
    ap=argparse.ArgumentParser(description='Validate frontend prototype freeze / implementation contract handoff.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--workflow')
    ap.add_argument('--risk', choices=['C','D'], default='C')
    ap.add_argument('--input-json')
    ap.add_argument('--write-artifacts', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    result=check_base(root)
    if args.workflow and args.write_artifacts:
        init_artifacts(root, Path(args.workflow), args.force)
    if args.workflow:
        wf_result=check_workflow(root, Path(args.workflow), args.risk, Path(args.input_json) if args.input_json else None)
        result={'status':'PASS' if result['status']=='PASS' and wf_result['status']=='PASS' else 'FAIL','base':result,'workflow':wf_result}
        if args.write_artifacts:
            wf=Path(args.workflow) if Path(args.workflow).is_absolute() else root/args.workflow
            out=wf/'frozen-prototype/prototype-freeze-gate-result.json'
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.format == 'json': print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']}")
        findings=result.get('findings') or result.get('base',{}).get('findings',[]) + result.get('workflow',{}).get('findings',[])
        for f in findings: print(f"{f['severity']}: {f.get('path','')}: {f['message']}")
    return 0 if result['status']=='PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
