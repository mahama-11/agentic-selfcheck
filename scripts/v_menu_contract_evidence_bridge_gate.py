#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, subprocess, time
from pathlib import Path
from v_governance_gate_common import ROOT, V_ROOT, validate_evidence_contract, load_json

FEATURE='v-menu-contract-evidence-bridge'
VERIFIER='v-menu-contract-evidence-bridge-gate'
MENU_BACKEND=V_ROOT/'menu-backend'
MENU_FRONTEND=V_ROOT/'menu-frontend'
REPORT_DIR=V_ROOT/'reports/evidence-contract/menu-studio-core-chain'
EVIDENCE_PATH=REPORT_DIR/'latest.json'
SECRET_RE=re.compile(r'(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+|((?:token|password|secret|api[_-]?key|authorization)\s*[:=]\s*)\S+|([?&](?:token|password|secret|api[_-]?key|authorization)=)[^&\s]+')
IP_RE=re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')

def redact(value):
    text=str(value)
    text=SECRET_RE.sub(lambda m: (m.group(1) or m.group(2) or m.group(3) or '')+'[REDACTED]', text)
    return IP_RE.sub('[REDACTED_IP]', text)

CRITICAL_ROUTES=[
  'POST /api/v1/menu/auth/register',
  'POST /api/v1/menu/auth/login',
  'GET /api/v1/menu/auth/session',
  'GET /api/v1/menu/user/credits',
  'GET /api/v1/menu/template-center/meta',
  'GET /api/v1/menu/template-center/catalog',
  'GET /api/v1/menu/template-center/catalog/:templateID',
  'POST /api/v1/menu/template-center/catalog/:templateID/use',
  'POST /api/v1/menu/template-center/catalog/:templateID/copy-to-my-templates',
  'GET /api/v1/menu/template-center/favorites',
  'POST /api/v1/menu/template-center/favorites/:templateID',
  'DELETE /api/v1/menu/template-center/favorites/:templateID',
  'POST /api/v1/menu/studio/assets',
  'GET /api/v1/menu/studio/assets',
  'GET /api/v1/menu/studio/library/assets',
  'GET /api/v1/menu/studio/styles',
  'POST /api/v1/menu/studio/styles',
  'GET /api/v1/menu/studio/styles/:styleID',
  'POST /api/v1/menu/studio/styles/:styleID/fork',
  'POST /api/v1/menu/studio/jobs',
  'GET /api/v1/menu/studio/jobs',
  'GET /api/v1/menu/studio/jobs/:jobID',
  'GET /api/v1/menu/studio/history/jobs',
  'POST /api/v1/menu/studio/jobs/:jobID/cancel',
  'POST /api/v1/menu/studio/jobs/:jobID/select-variant',
  'POST /internal/v1/menu/studio/jobs/:jobID/runtime',
  'POST /internal/v1/menu/studio/jobs/:jobID/results',
]
FRONTEND_PATTERNS=[
  ('src/services/auth.ts',['/auth/login','/auth/register','/auth/session','/user/credits']),
  ('src/services/studio.ts',['/studio/assets','/studio/library/assets','/studio/styles',"api.get<StylePreset, StylePreset>(`/studio/styles/${styleId}`)","api.post<StylePreset, StylePreset>(`/studio/styles/${styleId}/fork`",'/studio/jobs',"api.get<GenerationJob, GenerationJob>(`/studio/jobs/${jobId}`)",'/studio/history/jobs',"api.post<GenerationJob, GenerationJob>(`/studio/jobs/${jobId}/cancel`","api.post<GenerationJob, GenerationJob>(`/studio/jobs/${jobId}/select-variant`",'/studio/assets/${assetId}/content']),
  ('src/services/templateCenter.ts',['/template-center/meta','/template-center/catalog',"api.get<TemplateCatalogDetail, TemplateCatalogDetail>(`/template-center/catalog/${templateId}`",'/template-center/favorites',"api.post(`/template-center/favorites/${templateId}`)","api.delete(`/template-center/favorites/${templateId}`)","api.post<TemplateUseResult, TemplateUseResult>(`/template-center/catalog/${templateId}/use`","api.post<CopyTemplateResult, CopyTemplateResult>(`/template-center/catalog/${templateId}/copy-to-my-templates"]),
]

def emit_result(verifier, status, findings, extra=None):
    import json, time
    report_dir = V_ROOT / 'reports' / 'evidence-contract' / 'menu-studio-core-chain'
    report_dir.mkdir(parents=True, exist_ok=True)
    payload={'feature':'v-menu-contract-evidence-bridge','verifier':verifier,'status':status,'findings':findings,'extra':extra or {},'generated_at_epoch':time.time()}
    (report_dir / f'{verifier}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status in ('PASS','PASS_WITH_NOTES') else 1

def run(argv,cwd,timeout=180):
    started=time.time(); p=subprocess.run(argv,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    return {'command':redact(' '.join(argv)),'cwd':str(cwd),'exit_code':p.returncode,'duration_seconds':round(time.time()-started,3),'stdout_tail':redact(p.stdout[-1500:]),'stderr_tail':redact(p.stderr[-1500:])}

def swagger_paths():
    p=MENU_BACKEND/'docs/openapi/swagger.json'
    if not p.exists():
        return {}, [{'severity':'error','message':'missing Menu swagger.json','path':str(p)}]
    try:
        spec=load_json(p)
    except Exception as ex:
        return {}, [{'severity':'error','message':f'invalid Menu swagger.json: {ex}','path':str(p)}]
    paths=spec.get('paths') or {}
    return paths, []

def route_present(paths, route):
    method, raw = route.split(' ',1)
    swagger_path=re.sub(r':([A-Za-z0-9_]+)', r'{\1}', raw)
    if swagger_path in paths and method.lower() in paths[swagger_path]:
        return True, swagger_path
    # Some docs use :jobID while Swagger may use {jobID}; allow raw substring fallback only as advisory absent in swagger.
    return False, swagger_path

def frontend_sweep():
    findings=[]; sweep=[]
    for rel, pats in FRONTEND_PATTERNS:
        p=MENU_FRONTEND/rel
        item={'consumer':f'menu-frontend/{rel}','patterns':pats,'present':p.exists(),'missing':[]}
        if not p.exists():
            findings.append({'severity':'warning','message':'missing Menu frontend consumer file','path':str(p)})
        else:
            text=p.read_text(encoding='utf-8')
            for pat in pats:
                if pat not in text:
                    item['missing'].append(pat)
                    findings.append({'severity':'warning','message':'Menu frontend consumer missing expected route pattern','pattern':pat,'path':str(p)})
        sweep.append(item)
    return sweep, findings

def build_evidence(paths, route_hits, frontend_items, real_smoke=None, safe_smoke=None):
    missing=[r for r,h in route_hits.items() if not h.get('present')]
    real_api=[]; blind=[]
    if real_smoke and real_smoke.get('exit_code')==0:
        real_api.append({'type':'menu_real_contract_smoke','status':'PASS','command':real_smoke['command'],'exit_code':real_smoke['exit_code'],'stdout_tail':real_smoke.get('stdout_tail',''),'stderr_tail':real_smoke.get('stderr_tail','')})
        final_status='PASS_WITH_NOTES' if missing else 'PASS'
    else:
        real_api.append({'type':'menu_real_contract_smoke_not_run','status':'NOT_RUN','required_for_full_pass':True,'reason':'safe harness is registered; full pass requires explicitly approved local/dev execute mode with auth fixture and cleanup evidence'})
        if safe_smoke:
            real_api.append({'type':'menu_safe_smoke_harness','status':'PASS_WITH_NOTES' if safe_smoke.get('exit_code')==0 else 'FAIL','command':safe_smoke.get('command'),'exit_code':safe_smoke.get('exit_code'),'stdout_tail':safe_smoke.get('stdout_tail',''),'stderr_tail':safe_smoke.get('stderr_tail','')})
        final_status='PARTIAL_PASS'
        blind.append('real Menu Studio API/browser smoke not run; safe harness is dry-run only until approved local/dev fixture+cleanup are provided')
    if missing:
        blind.append('Menu swagger/OpenAPI does not yet publish every Studio/internal callback critical route: '+', '.join(missing[:8]))
    if any(i.get('missing') for i in frontend_items):
        blind.append('Menu frontend consumer sweep has missing expected route patterns')
    return {
      'feature_id':'menu-studio-core-chain-evidence-contract',
      'change_scope':'menu-studio-core-chain-openapi-frontend-consumer-readiness',
      'affected_services':['menu-backend','menu-frontend','platform-backend','agentic-selfcheck'],
      'affected_routes':CRITICAL_ROUTES,
      'auth_context':{'user_jwt':'required for Menu APIs','org_context':'required','internal_hmac':'required for internal runtime/callback','real_smoke':'not run unless explicitly approved local/dev'},
      'real_api_evidence':real_api,
      'browser_evidence':[{'status':'NOT_RUN','required':'Template Center -> Studio upload -> single/four-slot generation -> history/library desktop/mobile TH/EN/ZH'}],
      'contract_smoke_evidence':[{'type':'menu_swagger_route_inventory','status':'PARTIAL_PASS' if missing else 'PASS','schema':str((MENU_BACKEND/'docs/openapi/swagger.json').resolve()),'route_hits':route_hits},{'type':'menu_frontend_consumer_sweep','status':'PARTIAL_PASS' if any(i.get('missing') for i in frontend_items) else 'PASS','consumers':frontend_items}],
      'prod_dev_log_evidence':[{'status':'NOT_RUN','required_fields':['request_id','trace_id','runtime_job_id','callback_status','charge_session_id']}],
      'negative_cases':[{'case':'quota insufficient','expected':'fail-closed, no provider execution, no false success'},{'case':'bad internal HMAC','expected':'reject callback/internal request'},{'case':'provider failure/callback retry','expected':'job remains honest failed/retryable state'},{'case':'OpenAPI missing core route','expected':'bridge remains PARTIAL_PASS/PASS_WITH_NOTES with blind spot, never full PASS'}],
      'consumer_sweep':[{'consumer':x['consumer'],'status':'PARTIAL_PASS' if x.get('missing') else 'PASS','patterns':x['patterns'],'missing':x.get('missing',[])} for x in frontend_items] + [{'consumer':'platform runtime/storage/quota/wallet internal APIs','status':'REQUIRED_FOR_LIVE_SMOKE','paths':['runtime job','storage asset registry','quota reservation','charge session']}],
      'risk_level':'high',
      'rollback_path':{'type':'git_revert_or_disable_menu_release_promotion','paths':['menu-backend/docs/openapi','menu-frontend/src/services','agentic-selfcheck Menu bridge feature/verifiers']},
      'blind_spots':blind,
      'owner_role':'qa',
      'final_status':final_status,
    }

def main():
    findings=[]
    for p,label in [(MENU_BACKEND,'menu-backend'),(MENU_FRONTEND,'menu-frontend')]:
        if not p.exists(): findings.append({'severity':'error','message':f'missing {label}','path':str(p)})
    paths, errs=swagger_paths(); findings.extend(errs)
    route_hits={}
    for route in CRITICAL_ROUTES:
        ok, swagger_path=route_present(paths, route) if paths else (False, route)
        route_hits[route]={'present':ok,'swagger_path':swagger_path}
    frontend_items, frontend_findings=frontend_sweep(); findings.extend(frontend_findings)
    missing=[r for r,h in route_hits.items() if not h['present']]
    if missing:
        findings.append({'severity':'warning','message':'Menu OpenAPI missing critical routes; evidence remains partial','missing':missing})
    safe_smoke=run([os.environ.get('PYTHON','python3'),'scripts/v_menu_safe_contract_smoke.py','--dry-run','--env',os.environ.get('V_MENU_SMOKE_ENV','local'),'--base-url',os.environ.get('V_MENU_SMOKE_BASE_URL','http://127.0.0.1:8196'),'--platform-base-url',os.environ.get('V_MENU_SMOKE_PLATFORM_BASE_URL','http://127.0.0.1:8195')],ROOT,timeout=30)
    if safe_smoke.get('exit_code')!=0:
        findings.append({'severity':'error','message':'Menu safe smoke harness dry-run failed/refused','stdout_tail':safe_smoke.get('stdout_tail',''),'stderr_tail':safe_smoke.get('stderr_tail','')})
    real_smoke=None
    if os.environ.get('V_RUN_MENU_REAL_CONTRACT_SMOKE')=='1':
        real_smoke=run([os.environ.get('PYTHON','python3'),'scripts/v_menu_safe_contract_smoke.py','--execute','--env',os.environ.get('V_MENU_SMOKE_ENV','local'),'--base-url',os.environ.get('V_MENU_SMOKE_BASE_URL','http://127.0.0.1:8196'),'--platform-base-url',os.environ.get('V_MENU_SMOKE_PLATFORM_BASE_URL','http://127.0.0.1:8195')],ROOT,timeout=120)
        if real_smoke.get('exit_code')!=0:
            findings.append({'severity':'error','message':'approved Menu real contract smoke failed or was refused by safety harness','stdout_tail':real_smoke.get('stdout_tail',''),'stderr_tail':real_smoke.get('stderr_tail','')})
    evidence=build_evidence(paths, route_hits, frontend_items, real_smoke, safe_smoke)
    REPORT_DIR.mkdir(parents=True,exist_ok=True); EVIDENCE_PATH.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    findings.extend([{**f,'path':str(EVIDENCE_PATH)} for f in validate_evidence_contract(evidence)])
    status='FAIL' if any(f.get('severity')=='error' for f in findings) else 'PASS_WITH_NOTES'
    return emit_result(VERIFIER,status,findings,{'evidence_contract':str(EVIDENCE_PATH),'missing_openapi_routes':missing})
if __name__=='__main__': raise SystemExit(main())
