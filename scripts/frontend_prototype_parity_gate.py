#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, zlib
from pathlib import Path
from typing import Any

TEMPLATE_DIR = Path('templates/frontend/prototype-parity')
REQUIRED_TEMPLATES = ['PARITY_REPORT.md']
ALLOWED_TOP = {'schema_version','risk','workflow','prototype_freeze_evidence','threshold','overall_parity_score','verdict','coverage','comparisons','deviations','contract_needed_exceptions','approval'}
PASS_VERDICTS = {'PASS','PASS_WITH_APPROVED_DEVIATIONS'}


def finding(sev: str, path: Any, msg: str) -> dict:
    return {'severity': sev, 'path': str(path), 'message': msg}


def nonempty(p: Path, min_size: int = 40) -> bool:
    try:
        return p.exists() and p.is_file() and p.stat().st_size >= min_size
    except OSError:
        return False


def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding='utf-8'))


def is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def is_valid_png_data(data: bytes) -> bool:
    sig=b'\x89PNG\r\n\x1a\n'
    if len(data) < 57 or not data.startswith(sig):
        return False
    pos=len(sig); seen_ihdr=False; seen_idat=False; seen_iend=False
    width=height=bit_depth=color_type=None; idat=[]
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


def resolve_existing(root: Path, wf: Path, raw: str, allowed_bases: list[Path], must_be_file: bool=True) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    p=Path(raw.strip())
    candidates=[p] if p.is_absolute() else [wf/p, root/p]
    bases=[b.resolve() for b in allowed_bases]
    for c in candidates:
        try: r=c.resolve()
        except OSError: continue
        if not any(is_within(r, b) for b in bases):
            continue
        if not r.exists():
            continue
        if must_be_file and not r.is_file():
            continue
        return r
    return None


def schema_errors(root: Path) -> list[str]:
    p=root/'schemas/frontend-parity-report.schema.json'
    if not nonempty(p, 100): return ['frontend parity report schema missing or empty']
    try: json.loads(p.read_text(encoding='utf-8'))
    except Exception as exc: return [f'frontend parity report schema invalid JSON: {exc}']
    return []


def check_base(root: Path) -> dict:
    findings=[]
    for name in REQUIRED_TEMPLATES:
        p=root/TEMPLATE_DIR/name
        if not nonempty(p, 80): findings.append(finding('error', p, 'required prototype-parity template missing or empty'))
    for err in schema_errors(root): findings.append(finding('error', root/'schemas/frontend-parity-report.schema.json', err))
    return {'status':'PASS' if not findings else 'FAIL','scope':'base','findings':findings}


def structural_errors(data: Any) -> list[str]:
    if not isinstance(data, dict): return ['payload must be a JSON object']
    errors=[]; extra=set(data)-ALLOWED_TOP
    if extra: errors.append('unexpected top-level fields: ' + ', '.join(sorted(extra)))
    missing=ALLOWED_TOP-set(data)
    if missing: errors.append('missing required fields: ' + ', '.join(sorted(missing)))
    nested_allowed={
        'prototype_freeze_evidence': {'path','gate_result_path','status'},
        'threshold': {'minimum_score','scoring_basis'},
        'approval': {'owner','status','rationale','date','approved_at'},
    }
    nested_required={
        'prototype_freeze_evidence': {'path','status'},
        'threshold': {'minimum_score','scoring_basis'},
        'approval': {'owner','status','rationale'},
    }
    for key, allowed in nested_allowed.items():
        obj=data.get(key)
        if not isinstance(obj, dict): errors.append(f'{key} must be an object'); continue
        extra=set(obj)-allowed
        if extra: errors.append(f'{key} has unexpected fields: ' + ', '.join(sorted(extra)))
        miss=nested_required[key]-set(obj)
        if miss: errors.append(f'{key} missing required fields: ' + ', '.join(sorted(miss)))
    if isinstance(data.get('approval'), dict) and not (str(data['approval'].get('date','')).strip() or str(data['approval'].get('approved_at','')).strip()):
        errors.append('approval requires date or approved_at')
    for key in ['coverage','comparisons','deviations','contract_needed_exceptions']:
        if not isinstance(data.get(key), list): errors.append(f'{key} must be an array')
    return errors


def nonempty_string(obj: dict, key: str) -> bool:
    return isinstance(obj.get(key), str) and bool(obj.get(key,'').strip())


def freeze_screens(root: Path, wf: Path, report: dict, payload_path: Path, findings: list[dict]) -> dict[str, Path]:
    evidence=report.get('prototype_freeze_evidence') if isinstance(report.get('prototype_freeze_evidence'), dict) else {}
    freeze_path=resolve_existing(root, wf, evidence.get('path',''), [wf], True) if evidence else None
    gate_result=None
    if isinstance(evidence, dict) and evidence.get('gate_result_path'):
        gate_result=resolve_existing(root, wf, evidence.get('gate_result_path',''), [wf], True)
        if not gate_result: findings.append(finding('error', payload_path, 'prototype_freeze_evidence.gate_result_path must resolve under workflow'))
    if not freeze_path:
        findings.append(finding('error', payload_path, 'prototype_freeze_evidence.path must resolve to prototype-freeze.json under workflow'))
        return {}
    if freeze_path.name != 'prototype-freeze.json':
        findings.append(finding('error', freeze_path, 'prototype freeze evidence must be prototype-freeze.json'))
    if evidence.get('status') not in {'PASS','FROZEN','human_approved'}:
        findings.append(finding('error', payload_path, 'prototype_freeze_evidence.status must indicate PASS/FROZEN/human_approved'))
    if gate_result:
        try:
            gr=load_json(gate_result)
            if gr.get('status') != 'PASS': findings.append(finding('error', gate_result, 'freeze gate result is not PASS'))
        except Exception as exc:
            findings.append(finding('error', gate_result, f'freeze gate result invalid JSON: {exc}'))
    try:
        freeze=load_json(freeze_path)
    except Exception as exc:
        findings.append(finding('error', freeze_path, f'prototype-freeze.json invalid JSON: {exc}'))
        return {}
    items=freeze.get('frozen_screenshots')
    out={}
    if not isinstance(items, list) or not items:
        findings.append(finding('error', freeze_path, 'prototype freeze must include frozen_screenshots'))
        return out
    for i,item in enumerate(items):
        if not isinstance(item, dict):
            findings.append(finding('error', freeze_path, f'frozen_screenshots[{i}] must be an object')); continue
        screen=str(item.get('screen','')).strip()
        p=resolve_existing(root, wf, item.get('path',''), [wf/'prototype-screenshots', wf/'frozen-prototype'], True)
        if not screen:
            findings.append(finding('error', freeze_path, f'frozen_screenshots[{i}].screen is required'))
        if not p or not is_valid_png(p):
            findings.append(finding('error', freeze_path, f'frozen_screenshots[{i}].path must be a strict valid PNG under prototype-screenshots/ or frozen-prototype/'))
        elif screen:
            out[screen]=p
    return out


def check_workflow(root: Path, workflow: Path, risk: str, input_json: Path | None=None) -> dict:
    wf=workflow if workflow.is_absolute() else root/workflow
    risk=risk.upper(); findings=[]
    if not wf.exists():
        return {'status':'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'findings':[finding('error', wf, 'workflow does not exist')]}
    payload_path=input_json if input_json and input_json.is_absolute() else (root/input_json if input_json else wf/'frontend-parity-report.json')
    data=None
    if not payload_path.exists():
        findings.append(finding('error', payload_path, 'frontend parity report missing'))
    else:
        try: data=load_json(payload_path)
        except Exception as exc: findings.append(finding('error', payload_path, f'frontend parity report invalid JSON: {exc}'))
    prod_dir=wf/'production-screenshots'
    if not prod_dir.exists() or not prod_dir.is_dir():
        findings.append(finding('error', prod_dir, 'production-screenshots/ directory is required'))
    if data is None:
        return {'status':'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'payload':str(payload_path),'findings':findings}
    for err in structural_errors(data): findings.append(finding('error', payload_path, err))
    if data.get('schema_version') != '1.0': findings.append(finding('error', payload_path, 'schema_version must be 1.0'))
    if data.get('risk') != risk: findings.append(finding('error', payload_path, f'risk must match CLI risk {risk}'))
    if str(data.get('workflow','')).strip() not in {str(wf), wf.name}: findings.append(finding('error', payload_path, 'workflow must match workflow path or name'))
    threshold=data.get('threshold') if isinstance(data.get('threshold'), dict) else {}
    minimum=threshold.get('minimum_score', 80)
    if not isinstance(minimum, (int,float)) or minimum < 80:
        findings.append(finding('error', payload_path, 'threshold.minimum_score must be numeric and >= 80'))
        minimum=80
    score=data.get('overall_parity_score')
    if not isinstance(score, (int,float)) or score < minimum or score > 100:
        findings.append(finding('error', payload_path, f'overall_parity_score must be between {minimum} and 100'))
    if data.get('verdict') not in PASS_VERDICTS:
        findings.append(finding('error', payload_path, f'verdict must be one of {sorted(PASS_VERDICTS)}'))
    proto_screens=freeze_screens(root, wf, data, payload_path, findings)
    covered=set(); comparison_screens=set(); valid_prod=[]
    coverage=data.get('coverage') if isinstance(data.get('coverage'), list) else []
    for i,c in enumerate(coverage):
        if not isinstance(c, dict): findings.append(finding('error', payload_path, f'coverage[{i}] must be an object')); continue
        extra=set(c)-{'route','surface','prototype_screen','production_screenshot','status'}
        if extra: findings.append(finding('error', payload_path, f'coverage[{i}] has unexpected fields: ' + ', '.join(sorted(extra))))
        for key in ['route','surface','prototype_screen','production_screenshot','status']:
            if not nonempty_string(c, key): findings.append(finding('error', payload_path, f'coverage[{i}].{key} is required'))
        if c.get('status') not in {'covered','contract_needed'}: findings.append(finding('error', payload_path, f'coverage[{i}].status must be covered or contract_needed'))
        if c.get('status') == 'covered': covered.add(str(c.get('prototype_screen','')).strip())
        prod=resolve_existing(root, wf, c.get('production_screenshot',''), [prod_dir], True)
        if not prod or not is_valid_png(prod): findings.append(finding('error', payload_path, f'coverage[{i}].production_screenshot must be a strict valid PNG under production-screenshots/'))
        else: valid_prod.append(prod)
    comparisons=data.get('comparisons') if isinstance(data.get('comparisons'), list) else []
    if not comparisons: findings.append(finding('error', payload_path, 'comparisons must include at least one entry'))
    for i,c in enumerate(comparisons):
        if not isinstance(c, dict): findings.append(finding('error', payload_path, f'comparisons[{i}] must be an object')); continue
        extra=set(c)-{'route','surface','prototype_screen','prototype_screenshot','production_screenshot','parity_score','status','notes'}
        if extra: findings.append(finding('error', payload_path, f'comparisons[{i}] has unexpected fields: ' + ', '.join(sorted(extra))))
        for key in ['route','surface','prototype_screen','prototype_screenshot','production_screenshot','status']:
            if not nonempty_string(c, key): findings.append(finding('error', payload_path, f'comparisons[{i}].{key} is required'))
        ps=c.get('parity_score')
        if not isinstance(ps, (int,float)) or ps < minimum or ps > 100:
            findings.append(finding('error', payload_path, f'comparisons[{i}].parity_score must be between {minimum} and 100'))
        if c.get('status') not in {'pass','approved_deviation'}:
            findings.append(finding('error', payload_path, f'comparisons[{i}].status must be pass or approved_deviation'))
        screen=str(c.get('prototype_screen','')).strip(); comparison_screens.add(screen)
        proto=resolve_existing(root, wf, c.get('prototype_screenshot',''), [wf/'prototype-screenshots', wf/'frozen-prototype'], True)
        prod=resolve_existing(root, wf, c.get('production_screenshot',''), [prod_dir], True)
        if not proto or not is_valid_png(proto): findings.append(finding('error', payload_path, f'comparisons[{i}].prototype_screenshot must be a listed strict valid PNG under prototype-screenshots/ or frozen-prototype/'))
        elif screen and screen in proto_screens and proto.resolve() != proto_screens[screen].resolve():
            findings.append(finding('error', payload_path, f'comparisons[{i}].prototype_screenshot must match frozen screenshot for prototype_screen'))
        if not prod or not is_valid_png(prod): findings.append(finding('error', payload_path, f'comparisons[{i}].production_screenshot must be a strict valid PNG under production-screenshots/'))
        else: valid_prod.append(prod)
    missing=set(proto_screens)-covered
    if missing: findings.append(finding('error', payload_path, 'coverage missing frozen prototype screens: ' + ', '.join(sorted(missing))))
    missing_cmp=set(proto_screens)-comparison_screens
    if missing_cmp: findings.append(finding('error', payload_path, 'comparisons missing frozen prototype screens: ' + ', '.join(sorted(missing_cmp))))
    if not valid_prod: findings.append(finding('error', prod_dir, 'at least one real production screenshot PNG is required'))
    for i,d in enumerate(data.get('deviations') if isinstance(data.get('deviations'), list) else []):
        if not isinstance(d, dict): findings.append(finding('error', payload_path, f'deviations[{i}] must be an object')); continue
        extra=set(d)-{'description','material','approval_status','rationale'}
        if extra: findings.append(finding('error', payload_path, f'deviations[{i}] has unexpected fields: ' + ', '.join(sorted(extra))))
        for key in ['description','approval_status','rationale']:
            if not nonempty_string(d, key): findings.append(finding('error', payload_path, f'deviations[{i}].{key} is required'))
        if not isinstance(d.get('material'), bool): findings.append(finding('error', payload_path, f'deviations[{i}].material must be a boolean'))
        if d.get('material') is True and d.get('approval_status') not in {'approved','human_approved'}:
            findings.append(finding('error', payload_path, f'deviations[{i}] material deviation requires approved or human_approved approval_status'))
        if risk == 'D' and d.get('material') is True and d.get('approval_status') != 'human_approved':
            findings.append(finding('error', payload_path, f'deviations[{i}] D-risk material deviation requires human_approved'))
    for i,e in enumerate(data.get('contract_needed_exceptions') if isinstance(data.get('contract_needed_exceptions'), list) else []):
        if not isinstance(e, dict): findings.append(finding('error', payload_path, f'contract_needed_exceptions[{i}] must be an object')); continue
        extra=set(e)-{'scope','visual_parity_scope','owner','approval_status','rationale'}
        if extra: findings.append(finding('error', payload_path, f'contract_needed_exceptions[{i}] has unexpected fields: ' + ', '.join(sorted(extra))))
        for key in ['scope','owner','approval_status','rationale']:
            if not nonempty_string(e, key): findings.append(finding('error', payload_path, f'contract_needed_exceptions[{i}].{key} is required'))
        if e.get('approval_status') not in {'approved','human_approved'}:
            findings.append(finding('error', payload_path, f'contract_needed_exceptions[{i}] requires explicit approved/human_approved status'))
        if e.get('visual_parity_scope') is not False:
            findings.append(finding('error', payload_path, f'contract_needed_exceptions[{i}] cannot bypass visual parity; visual_parity_scope must be false'))
    approval=data.get('approval') if isinstance(data.get('approval'), dict) else {}
    if approval.get('status') not in ({'accepted','human_approved'} if risk == 'C' else {'human_approved'}):
        findings.append(finding('error', payload_path, f'approval.status invalid for {risk}-risk'))
    for key in ['owner','rationale']:
        if not str(approval.get(key,'')).strip(): findings.append(finding('error', payload_path, f'approval.{key} is required'))
    return {'status':'PASS' if not findings else 'FAIL','scope':'workflow','risk':risk,'workflow':str(wf),'payload':str(payload_path),'production_screenshots':[str(p) for p in sorted(set(valid_prod))],'prototype_screens':sorted(proto_screens),'findings':findings}


def init_artifacts(root: Path, workflow: Path, force: bool=False) -> list[str]:
    wf=workflow if workflow.is_absolute() else root/workflow
    wf.mkdir(parents=True, exist_ok=True); (wf/'production-screenshots').mkdir(exist_ok=True)
    out=[]; tmpl=root/TEMPLATE_DIR
    for name in REQUIRED_TEMPLATES:
        target=wf/name
        if target.exists() and not force: continue
        shutil.copyfile(tmpl/name, target); out.append(str(target))
    return out


def main() -> int:
    ap=argparse.ArgumentParser(description='Validate prototype-to-production parity evidence for C/D frontend work.')
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
            out=wf/'prototype-parity-gate-result.json'
            out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.format == 'json': print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']}")
        findings=result.get('findings') or result.get('base',{}).get('findings',[]) + result.get('workflow',{}).get('findings',[])
        for f in findings: print(f"{f['severity']}: {f.get('path','')}: {f['message']}")
    return 0 if result['status']=='PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
