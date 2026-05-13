#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path
from typing import Any

import yaml

REQUIRED_PRODUCTION_GATES = [
    'frontend-design-quality-pack-gate',
    'frontend-design-lane-generation-gate',
    'frontend-high-fidelity-prototype-gate',
    'frontend-prototype-freeze-gate',
    'frontend-prototype-parity-gate',
]
PROTOTYPE_FIRST_GATES = REQUIRED_PRODUCTION_GATES[:4]
FRONTEND_PATH_HINTS = ('frontend/', '-frontend/', 'src/pages/', 'src/components/', 'src/views/', 'app/routes/', 'routes/', 'templates/', '.tsx', '.jsx', '.vue', '.svelte', '.html', '.css', '.scss')
PRODUCTION_TERMS = ('production','implementation','implement','build','ship','release','real project','production code')
C_RISK_TERMS = ('redesign','page','screen','flow','interaction','navigation','dashboard','workbench','prototype','visual hierarchy','new ui','route')
D_RISK_TERMS = ('checkout','payment','billing','wallet','public pricing','public page','brand','mission critical','core funnel','human signoff')
B_RISK_TERMS = ('copy-only','copy only','text only','label','small copy','typo','color token')


def load_yaml(path: Path) -> dict[str, Any]:
    data=yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path} must contain a YAML object')
    return data


def finding(severity: str, path: str, message: str) -> dict[str, str]:
    return {'severity': severity, 'path': path, 'message': message}


def is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def safe_input_path(root: Path, raw: str) -> tuple[Path | None, dict[str, str] | None]:
    p=Path(raw)
    candidate=p if p.is_absolute() else root/p
    try:
        resolved=candidate.resolve()
    except OSError as exc:
        return None, finding('error', raw, f'input path cannot be resolved: {exc}')
    if not is_within(resolved, root):
        return None, finding('error', str(resolved), 'input path must stay under --root')
    if not resolved.exists() or not resolved.is_file():
        return None, finding('error', str(resolved), 'input file missing')
    return resolved, None


def static_gates(feature: dict[str, Any]) -> list[str]:
    mp=feature.get('must_pass') if isinstance(feature.get('must_pass'), dict) else {}
    gates=[]
    for group in ('static','browser','api','evidence'):
        values=mp.get(group, []) if isinstance(mp.get(group, []), list) else []
        gates.extend(str(v) for v in values)
    return gates


def feature_risk(feature: dict[str, Any]) -> str:
    gov=feature.get('governance') if isinstance(feature.get('governance'), dict) else {}
    for key in ('risk_level','frontend_risk','risk'):
        value=str(gov.get(key, '')).upper()
        if value in {'A','B','C','D'}:
            return value
    levels=gov.get('risk_levels') or gov.get('applies_to_risks') or []
    if isinstance(levels, list):
        ordered=[str(x).upper() for x in levels if str(x).upper() in {'A','B','C','D'}]
        if ordered:
            return max(ordered, key=lambda x: 'ABCD'.index(x))
    return 'UNKNOWN'


def is_frontend_feature(feature: dict[str, Any]) -> bool:
    dims={str(x) for x in feature.get('risk_dimensions', []) if isinstance(x, str)}
    if 'frontend' in dims:
        return True
    targets=feature.get('target_services') if isinstance(feature.get('target_services'), dict) else {}
    if 'frontend' in targets:
        return True
    text=' '.join(str(feature.get(k,'')) for k in ('id','description')).lower()
    return any(h.strip('/.') in text for h in ('frontend','ui','screen','page'))


def requires_production_chain(feature: dict[str, Any]) -> bool:
    gov=feature.get('governance') if isinstance(feature.get('governance'), dict) else {}
    policy=str(gov.get('frontend_route_policy','')).lower()
    phase=str(gov.get('phase','')).lower()
    if policy in {'production-implementation','implementation','prototype-first-production'}:
        return True
    if phase in {'production-implementation','implementation'}:
        return True
    if bool(gov.get('production_implementation') is True):
        return True
    text=' '.join(str(feature.get(k,'')) for k in ('id','description')).lower()
    return not bool(gov.get('generic') is True) and any(term in text for term in PRODUCTION_TERMS)


def validate_feature(path: Path, feature: dict[str, Any]) -> dict[str, Any]:
    findings=[]
    risk=feature_risk(feature)
    frontend=is_frontend_feature(feature)
    gates=static_gates(feature)
    required=[]
    if frontend and requires_production_chain(feature):
        if risk == 'UNKNOWN':
            findings.append(finding('error', str(path), 'production frontend work must declare governance.risk_level/frontend_risk/risk or risk_levels/applies_to_risks'))
        elif risk in {'C','D'}:
            required=REQUIRED_PRODUCTION_GATES
            missing=[g for g in required if g not in gates]
            if missing:
                findings.append(finding('error', str(path), 'C/D production frontend work must route through prototype-first gates before/after implementation; missing: ' + ', '.join(missing)))
    return {
        'status':'PASS' if not findings else 'FAIL',
        'scope':'feature',
        'feature':feature.get('id'),
        'frontend':frontend,
        'risk':risk,
        'required_gates':required,
        'present_gates':gates,
        'findings':findings,
    }


def classify_task(task: dict[str, Any]) -> dict[str, Any]:
    text=' '.join(str(task.get(k,'')) for k in ('id','title','description','summary')).lower()
    files=[str(x).replace('\\','/') for x in task.get('changed_files', []) if isinstance(x, str)]
    file_text=' '.join(files).lower()
    frontend=any(h in file_text for h in FRONTEND_PATH_HINTS) or any(t in text for t in ('frontend','ui','screen','page','visual','react'))
    risk='A'
    reasons=[]
    if frontend:
        risk='B'; reasons.append('frontend surface touched')
        if any(term in text for term in B_RISK_TERMS) and not any(term in text for term in C_RISK_TERMS + D_RISK_TERMS):
            risk='B'; reasons.append('copy/token-only language')
        if any(term in text for term in C_RISK_TERMS):
            risk='C'; reasons.append('page/flow/visual product change')
        if any(term in text for term in D_RISK_TERMS):
            risk='D'; reasons.append('critical/public/commercial frontend surface')
    route=[]
    required_gates=[]
    if frontend and risk in {'C','D'}:
        route=[
            'design-quality-pack',
            'design-lane-generation',
            'high-fidelity-prototype-coverage-gate',
            'prototype-freeze-before-implementation',
            'prototype-parity-after-implementation',
        ]
        required_gates=REQUIRED_PRODUCTION_GATES
    elif frontend:
        route=['lightweight-frontend-review']
    else:
        route=['non-frontend-default']
    return {'status':'PASS','scope':'task','task':task.get('id') or task.get('title'),'frontend':frontend,'risk':risk,'reasons':reasons,'route':route,'required_gates':required_gates}


def init_workflow(root: Path, task: dict[str, Any], classification: dict[str, Any]) -> str | None:
    if not classification.get('frontend') or classification.get('risk') not in {'C','D'}:
        return None
    name=str(task.get('id') or task.get('title') or 'frontend-task')
    title=str(task.get('title') or name)
    cmd=[sys.executable,'scripts/init_frontend_workflow.py','--root',str(root),'--name',name,'--risk',classification['risk'],'--project',str(task.get('project','unspecified')),'--title',title,'--force']
    cp=subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or cp.stdout.strip() or 'init_frontend_workflow failed')
    return cp.stdout.strip().splitlines()[-1]


def main() -> int:
    ap=argparse.ArgumentParser(description='Route frontend tasks/features by risk; enforce prototype-first gates for C/D production implementation.')
    ap.add_argument('--root', default='.')
    ap.add_argument('--feature-file', action='append', default=[])
    ap.add_argument('--scan-features', action='store_true')
    ap.add_argument('--task-json')
    ap.add_argument('--expect-risk', choices=['A','B','C','D'])
    ap.add_argument('--init-workflow', action='store_true')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    results=[]; findings=[]
    feature_files=[Path(p) for p in args.feature_file]
    if args.scan_features:
        feature_files += sorted((root/'features').glob('*.yaml'))
    for p in feature_files:
        resolved, err=safe_input_path(root, str(p))
        if err:
            res={'status':'FAIL','scope':'feature','feature':None,'frontend':None,'risk':None,'required_gates':[],'present_gates':[],'findings':[err]}
            results.append(res); findings.append(err); continue
        feature=load_yaml(resolved)
        res=validate_feature(resolved, feature)
        results.append(res); findings.extend(res.get('findings', []))
    if args.task_json:
        task_path, err=safe_input_path(root, args.task_json)
        if err:
            res={'status':'FAIL','scope':'task','task':None,'frontend':None,'risk':None,'findings':[err]}
            results.append(res); findings.append(err)
        else:
            task=json.loads(task_path.read_text(encoding='utf-8'))
            res=classify_task(task)
            if args.expect_risk and res['risk'] != args.expect_risk:
                res['status']='FAIL'
                res.setdefault('findings', []).append(finding('error', str(task_path), f'expected risk {args.expect_risk}, got {res["risk"]}'))
            if args.init_workflow:
                try:
                    res['initialized_workflow']=init_workflow(root, task, res)
                except Exception as exc:
                    res['status']='FAIL'; res.setdefault('findings', []).append(finding('error', str(task_path), str(exc)))
            results.append(res); findings.extend(res.get('findings', []))
    status='PASS' if not findings and all(r.get('status') == 'PASS' for r in results) else 'FAIL'
    report={'status':status,'results':results,'findings':findings}
    outdir=root/'reports/frontend-risk-routing'
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir/'latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.format == 'json': print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('status=' + status)
        for r in results:
            label=r.get('feature') or r.get('task') or r.get('scope')
            print(f"{label}: risk={r.get('risk')} frontend={r.get('frontend')} status={r.get('status')}")
        for f in findings: print(f"{f['severity']}: {f['path']}: {f['message']}")
    return 0 if status == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
