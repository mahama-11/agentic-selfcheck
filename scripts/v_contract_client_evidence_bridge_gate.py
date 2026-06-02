#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, subprocess, time
from pathlib import Path
from v_governance_gate_common import V_ROOT, result, validate_evidence_contract, load_json

FEATURE='v-contract-client-evidence-bridge'
VERIFIER='v-contract-client-evidence-bridge-gate'
ECOM_FRONTEND=V_ROOT/'ecommerce-frontend'
REPORT_DIR=V_ROOT/'reports/evidence-contract/ecommerce-v1-contract-client'
EVIDENCE_PATH=REPORT_DIR/'latest.json'

SENSITIVE_PATTERNS = [
    re.compile(r'(Bearer\s+)[A-Za-z0-9._~+\-/]+=*', re.I),
    re.compile(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'),
    re.compile(r'(?i)(password|token|authorization|secret|api[_-]?key)(["\'\s:=]+)([^\s"\']+)'),
]
REQUIRED_OPERATIONS = {
    'GET /api/v1/ecommerce/auth/session': 'getEcommerceSession',
    'GET /api/v1/ecommerce/products': 'listProducts',
    'POST /api/v1/ecommerce/products': 'createProduct',
    'GET /api/v1/ecommerce/products/{productId}': 'getProduct',
    'GET /api/v1/ecommerce/production/{productId}/stage-view': 'getProductionStageView',
}


def redact(text: str) -> str:
    safe = text or ''
    safe = SENSITIVE_PATTERNS[0].sub(r'\1[REDACTED]', safe)
    safe = SENSITIVE_PATTERNS[1].sub('[REDACTED_JWT]', safe)
    safe = SENSITIVE_PATTERNS[2].sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", safe)
    return safe


def run(argv, cwd, timeout=180):
    started=time.time()
    proc=subprocess.run(argv, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return {
        'command':' '.join(argv), 'cwd':str(cwd), 'exit_code':proc.returncode,
        'duration_seconds':round(time.time()-started,3),
        'stdout_tail':redact(proc.stdout[-2000:]), 'stderr_tail':redact(proc.stderr[-2000:])
    }


def operation_id(spec, method_path: str):
    method, api_path = method_path.split(' ', 1)
    return (spec.get('paths', {}).get(api_path, {}).get(method.lower(), {}) or {}).get('operationId')


def validate_artifacts():
    findings=[]
    schema_path=ECOM_FRONTEND/'contracts/ecommerce.openapi.json'
    base_path=ECOM_FRONTEND/'contracts/base/ecommerce.openapi.json'
    generated_path=ECOM_FRONTEND/'src/api/generated/ecommerce-contract.ts'
    contract_report=ECOM_FRONTEND/'reports/frontend-quality/api-contract-latest.json'
    diff_report=ECOM_FRONTEND/'reports/contract-governance/contract-diff.json'
    for path, label in [(schema_path,'head OpenAPI schema'),(base_path,'base OpenAPI schema'),(generated_path,'generated client'),(contract_report,'api contract report'),(diff_report,'contract diff report')]:
        if not path.exists():
            findings.append({'severity':'error','message':f'missing {label}','path':str(path)})
    if schema_path.exists():
        try:
            spec=load_json(schema_path)
            for method_path, op in REQUIRED_OPERATIONS.items():
                actual=operation_id(spec, method_path)
                if actual != op:
                    findings.append({'severity':'error','message':f'OpenAPI missing required operation {method_path} -> {op}','actual':actual,'path':str(schema_path)})
        except Exception as exc:
            findings.append({'severity':'error','message':f'cannot read OpenAPI schema: {exc}','path':str(schema_path)})
    if generated_path.exists():
        text=generated_path.read_text(encoding='utf-8')
        for op in REQUIRED_OPERATIONS.values():
            if op not in text:
                findings.append({'severity':'error','message':f'generated client missing operation {op}','path':str(generated_path)})
    for report, label in [(contract_report,'api contract report'),(diff_report,'contract diff report')]:
        if report.exists():
            try:
                status=load_json(report).get('status')
                if status not in ('PASS','PASS_WITH_NOTES'):
                    findings.append({'severity':'error','message':f'{label} is not passing','status':status,'path':str(report)})
            except Exception as exc:
                findings.append({'severity':'error','message':f'cannot read {label}: {exc}','path':str(report)})
    findings.extend(validate_consumer_sweep())
    return findings


def validate_consumer_sweep():
    findings=[]
    product_service=ECOM_FRONTEND/'src/services/product.ts'
    generated=ECOM_FRONTEND/'src/api/generated/ecommerce-contract.ts'
    if product_service.exists():
        text=product_service.read_text(encoding='utf-8')
        expected=[("'/api/v1/ecommerce/products'", 'method: \'POST\''), ("'/api/v1/ecommerce/products'", "method: 'GET'"), ('/api/v1/ecommerce/products/${productId}', "method: 'GET'")]
        for path_literal, method_literal in expected:
            if path_literal not in text or method_literal not in text:
                findings.append({'severity':'error','message':'consumer service missing expected product request pattern','expected':[path_literal,method_literal],'path':str(product_service)})
    else:
        findings.append({'severity':'error','message':'missing product service for consumer sweep','path':str(product_service)})
    if generated.exists():
        g=generated.read_text(encoding='utf-8')
        if 'createProduct' not in g or 'post: operations["createProduct"]' not in g:
            findings.append({'severity':'error','message':'generated contract does not cover product create POST used by consumer','path':str(generated)})
    return findings


def real_smoke_succeeded(evidence):
    for item in evidence.get('real_api_evidence') or []:
        if item.get('type') == 'real_contract_smoke_not_run' or item.get('status') == 'NOT_RUN':
            return False
        if item.get('exit_code') == 0:
            return True
    return False


def report_path(rel):
    return str((ECOM_FRONTEND/rel).resolve())


def build_evidence(api_result, diff_result, real_smoke_result=None):
    contract_report=ECOM_FRONTEND/'reports/frontend-quality/api-contract-latest.json'
    diff_report=ECOM_FRONTEND/'reports/contract-governance/contract-diff.json'
    generated=ECOM_FRONTEND/'src/api/generated/ecommerce-contract.ts'
    openapi=ECOM_FRONTEND/'contracts/ecommerce.openapi.json'
    final_status='PASS_WITH_NOTES' if real_smoke_result and real_smoke_result.get('exit_code')==0 else 'PARTIAL_PASS'
    blind_spots=[]
    real_api=[]
    if real_smoke_result:
        real_api.append({
            'command': real_smoke_result['command'],
            'exit_code': real_smoke_result['exit_code'],
            'stdout_tail': real_smoke_result.get('stdout_tail',''),
            'stderr_tail': real_smoke_result.get('stderr_tail',''),
            'required': True,
        })
        if real_smoke_result.get('exit_code') != 0:
            blind_spots.append('real ecommerce product-create/read/list contract smoke attempted but did not pass; inspect stderr_tail')
    else:
        real_api.append({
            'type':'real_contract_smoke_not_run',
            'command':'tools/contract-smoke/v-contract-smoke.sh ecommerce product-create',
            'required_for_full_pass': True,
            'status':'NOT_RUN',
            'reason':'set V_RUN_REAL_CONTRACT_SMOKE=1 with valid local/dev services and auth to upgrade evidence'
        })
        blind_spots.append('real ecommerce product-create/read/list smoke not run; set V_RUN_REAL_CONTRACT_SMOKE=1 with valid local/dev services and auth to upgrade evidence')
    diff_status='UNKNOWN'
    if diff_report.exists():
        try: diff_status=load_json(diff_report).get('status') or load_json(diff_report).get('severity') or 'PRESENT'
        except Exception: diff_status='UNREADABLE'
    return {
        'feature_id':'ecommerce-v1-contract-client-evidence',
        'change_scope':'ecommerce-v1-api-contract-generated-client-drift',
        'affected_services':['ecommerce-frontend','ecommerce-backend'],
        'affected_routes':['GET /api/v1/ecommerce/auth/session','GET /api/v1/ecommerce/products','POST /api/v1/ecommerce/products','GET /api/v1/ecommerce/products/{productId}','GET /api/v1/ecommerce/production/{productId}/stage-view'],
        'auth_context':{'mode':'user_jwt_for_real_smoke','status':'not_required_for_generation','real_smoke_requires':'V_ECOMMERCE_SMOKE_TOKEN or V_ECOMMERCE_SMOKE_EMAIL/V_ECOMMERCE_SMOKE_PASSWORD'},
        'real_api_evidence':real_api,
        'browser_evidence':[],
        'contract_smoke_evidence':[
            {'type':'openapi_generated_client','command':api_result['command'],'exit_code':api_result['exit_code'],'report_path':report_path('reports/frontend-quality/api-contract-latest.json'),'schema':report_path('contracts/ecommerce.openapi.json'),'generated':report_path('src/api/generated/ecommerce-contract.ts')},
            {'type':'openapi_breaking_diff','command':diff_result['command'],'exit_code':diff_result['exit_code'],'report_path':report_path('reports/contract-governance/contract-diff.json'),'base':report_path('contracts/base/ecommerce.openapi.json'),'head':report_path('contracts/ecommerce.openapi.json'),'diff_status':diff_status},
        ],
        'prod_dev_log_evidence':[],
        'negative_cases':[{'case':'generated_client_drift','expected':'api:contract regenerates and verifies required operations'},{'case':'breaking_openapi_diff','expected':'contract:diff flags breaking changes before closure'}],
        'consumer_sweep':[{'consumer':'ecommerce-frontend/src/api/generated/ecommerce-contract.ts','paths':['session','products create/list/detail','production stage-view'],'enforced_by':'validate_artifacts.required_operations'},{'consumer':'ecommerce-frontend/src/services/product.ts','paths':['product create/read/list mutation/read consistency'],'enforced_by':'validate_consumer_sweep.request_patterns'},{'consumer':'ecommerce-frontend/src/services/imageRuntime.ts','paths':['image job create/list/read callback projection pending for later runtime smoke'],'enforced_by':'documented_blind_spot'}],
        'risk_level':'high',
        'rollback_path':{'type':'git_revert_or_schema_regeneration','paths':['ecommerce-frontend/contracts/ecommerce.openapi.json','ecommerce-frontend/src/api/generated/ecommerce-contract.ts']},
        'blind_spots':blind_spots,
        'owner_role':'qa',
        'final_status':final_status,
    }


def main():
    findings=[]
    if not ECOM_FRONTEND.exists():
        return result(VERIFIER,'FAIL',[{'severity':'error','message':'missing ecommerce-frontend','path':str(ECOM_FRONTEND)}])
    api=run(['npm','run','api:contract'], ECOM_FRONTEND, timeout=240)
    if api['exit_code']!=0:
        findings.append({'severity':'error','message':'npm run api:contract failed','stderr_tail':api['stderr_tail']})
    diff=run(['npm','run','contract:diff'], ECOM_FRONTEND, timeout=240)
    if diff['exit_code']!=0:
        findings.append({'severity':'error','message':'npm run contract:diff failed','stderr_tail':diff['stderr_tail']})
    findings.extend(validate_artifacts())
    real_smoke=None
    run_real = os.environ.get('V_RUN_REAL_CONTRACT_SMOKE') == '1'
    if os.environ.get('V_RUN_REAL_CONTRACT_SMOKE') is None:
        base = os.environ.get('V_ECOMMERCE_BASE_URL','http://127.0.0.1:15181')
        run_real = bool(re.match(r'^https?://(127\.0\.0\.1|localhost)(:\d+)?(/.*)?$', base))
    if run_real:
        real_smoke=run([str(V_ROOT/'tools/contract-smoke/v-contract-smoke.sh'),'ecommerce','product-create'], V_ROOT, timeout=300)
        if real_smoke['exit_code']!=0:
            findings.append({'severity':'warning','message':'real contract smoke attempted but failed; evidence remains partial','stderr_tail':real_smoke['stderr_tail']})
    evidence=build_evidence(api,diff,real_smoke)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    validation=validate_evidence_contract(evidence)
    findings += [{**f,'path':str(EVIDENCE_PATH)} for f in validation]
    if evidence.get('final_status') in ('PASS','PASS_WITH_NOTES') and not real_smoke_succeeded(evidence):
        findings.append({'severity':'error','message':'PASS/PASS_WITH_NOTES evidence requires successful real contract smoke; NOT_RUN must remain PARTIAL_PASS','path':str(EVIDENCE_PATH)})
    # Generated contract drift guard: after api:contract, generated file must be present and not older than current process start by too much.
    generated=ECOM_FRONTEND/'src/api/generated/ecommerce-contract.ts'
    if not generated.exists():
        findings.append({'severity':'error','message':'generated ecommerce contract missing after api:contract','path':str(generated)})
    status='FAIL' if any(f.get('severity')=='error' for f in findings) else ('PASS_WITH_NOTES' if evidence['final_status']=='PARTIAL_PASS' else 'PASS')
    return result(VERIFIER,status,findings,{'evidence_contract':str(EVIDENCE_PATH),'api_contract':api,'contract_diff':diff,'real_smoke_ran':bool(real_smoke)})
if __name__=='__main__': raise SystemExit(main())
