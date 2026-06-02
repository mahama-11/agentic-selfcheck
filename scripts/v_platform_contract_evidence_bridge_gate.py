#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, subprocess, time
from pathlib import Path
from v_governance_gate_common import V_ROOT, result, validate_evidence_contract, load_json

VERIFIER='v-platform-contract-evidence-bridge-gate'
PLATFORM=V_ROOT/'platform-backend'
REPORT_DIR=V_ROOT/'reports/evidence-contract/platform-shared-capabilities'
EVIDENCE_PATH=REPORT_DIR/'latest.json'
REQUIRED_ROUTES={
  'auth_context':['POST /api/v1/auth/register','POST /api/v1/auth/login','GET /api/v1/auth/me'],
  'runtime_provider_route':['POST /internal/v1/runtime/providers','GET /internal/v1/runtime/providers','GET /internal/v1/runtime/capabilities','POST /internal/v1/runtime/jobs','GET /internal/v1/runtime/jobs/:runtimeJobID','PUT /internal/v1/runtime/jobs/:runtimeJobID','POST /internal/v1/runtime/jobs/:runtimeJobID/cancel','POST /internal/v1/runtime/jobs/:runtimeJobID/attempts','POST /api/v1/runtime/providers/:providerCode/callback'],
  'quota_reservation':['POST /internal/v1/controls/reservations','POST /internal/v1/controls/reservations/:reservationID/commit','POST /internal/v1/controls/reservations/:reservationID/release','POST /internal/v1/controls/quota/grants','GET /internal/v1/controls/quota/balance'],
  'storage_asset_registry':['POST /internal/v1/storage/assets','POST /internal/v1/storage/assets/register','POST /internal/v1/storage/assets/import-local','POST /internal/v1/storage/assets/resolve','GET /internal/v1/storage/assets/metadata','GET /internal/v1/storage/assets/content'],
  'wallet_metering_settlement':['POST /internal/v1/runtime/charge-sessions','GET /internal/v1/runtime/charge-sessions/:chargeSessionID','PUT /internal/v1/runtime/charge-sessions/:chargeSessionID','GET /internal/v1/wallet/summary','POST /internal/v1/wallet/ledger','POST /internal/v1/metering/events','POST /internal/v1/metering/finalizations','GET /internal/v1/metering/settlements'],
  'internal_auth_hmac':['internal.Use(middleware.RequireInternalService(cfg.Security.InternalServiceSecret))'],
}
SENSITIVE=[re.compile(r'(Bearer[ \t]+)[A-Za-z0-9._~+\-/]+=*',re.I),re.compile(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'),re.compile(r'(?i)(password|token|authorization|secret|api[_-]?key)(["\' \t:=]+)([^\n\r\s"\']+)'),re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),re.compile(r'\b[A-Za-z0-9._-]+@(?:\d{1,3}\.){3}\d{1,3}\b'),re.compile(r'\b[A-Za-z0-9._-]+@[A-Za-z0-9._-]+\.[A-Za-z]{2,}\b'),re.compile(r'(?i)(\bssh[ \t]+)([^\s]+)')]

def redact(s):
    s=s or ''
    s=SENSITIVE[0].sub(r'\1[REDACTED]',s); s=SENSITIVE[1].sub('[REDACTED_JWT]',s); s=SENSITIVE[2].sub(lambda m:f"{m.group(1)}{m.group(2)}[REDACTED]",s)
    s=SENSITIVE[6].sub(r'\1[REDACTED_SSH_TARGET]', s)
    s=SENSITIVE[5].sub('[REDACTED_SSH_TARGET]', s)
    s=SENSITIVE[4].sub('[REDACTED_SSH_TARGET]', s)
    s=SENSITIVE[3].sub('[REDACTED_IP]', s)
    s=re.sub(r'(?i)(remote=)[^\s]+', r'\1[REDACTED]', s)
    return s

def run(argv,cwd,timeout=180):
    started=time.time(); p=subprocess.run(argv,cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    return {'command':' '.join(argv),'cwd':str(cwd),'exit_code':p.returncode,'duration_seconds':round(time.time()-started,3),'stdout_tail':redact(p.stdout[-2000:]),'stderr_tail':redact(p.stderr[-2000:])}

def router_routes():
    contract_test=PLATFORM/'internal/router/platform_contract_routes_test.go'
    router=PLATFORM/'internal/router/router.go'
    findings=[]; route_hits={}
    if not router.exists():
        return {}, [{'severity':'error','message':'missing router.go','path':str(router)}]
    if not contract_test.exists():
        return {}, [{'severity':'error','message':'missing Platform contract route test','path':str(contract_test)}]
    router_text=router.read_text(encoding='utf-8')
    test_text=contract_test.read_text(encoding='utf-8')
    for capability,routes in REQUIRED_ROUTES.items():
        route_hits[capability]=[]
        for route in routes:
            if route.startswith('internal.Use('):
                ok=route in router_text
                proof='router.go middleware'
            else:
                ok=route in test_text
                proof='go test ./internal/router -run TestPlatformSharedCapabilityContractRoutes uses engine.Routes() full METHOD path inventory'
            route_hits[capability].append({'route':route,'present':ok,'proof':proof})
            if not ok:
                findings.append({'severity':'error','message':f'missing required Platform contract route test coverage for {capability}: {route}','path':str(contract_test)})
    return route_hits, findings

def dry_runtime_smoke():
    script=V_ROOT/'tools/contract-smoke/platform-shared-capability-smoke.sh'
    if not script.exists():
        return {'status':'MISSING','path':str(script)}, [{'severity':'error','message':'missing platform shared capability smoke harness','path':str(script)}]
    r=run([str(script),'--env','local','--dry-run'], V_ROOT, timeout=120)
    findings=[]
    if r['exit_code']!=0:
        findings.append({'severity':'error','message':'platform shared capability smoke dry-run failed','stderr_tail':r['stderr_tail']})
    prod_refusal=run([str(script),'--env','prod','--dry-run'], V_ROOT, timeout=120)
    if prod_refusal['exit_code'] != 2:
        findings.append({'severity':'error','message':'platform shared capability smoke must refuse prod by default','exit_code':prod_refusal['exit_code']})
    prod_url_refusal=run([str(script),'--env','local','--dry-run','--base-url','https://prod.example.com'], V_ROOT, timeout=120)
    if prod_url_refusal['exit_code'] != 2:
        findings.append({'severity':'error','message':'platform shared capability smoke must refuse prod-like base URL even when env is local/dev','exit_code':prod_url_refusal['exit_code']})
    r['prod_refusal_exit_code']=prod_refusal['exit_code']
    r['prod_refusal_stderr_tail']=prod_refusal.get('stderr_tail','')
    r['prod_url_refusal_exit_code']=prod_url_refusal['exit_code']
    r['prod_url_refusal_stderr_tail']=prod_url_refusal.get('stderr_tail','')
    return r, findings

def build_evidence(route_hits, router_test, dry_smoke, live_smoke=None):
    real_api = []
    blind_spots = []
    final_status = 'PARTIAL_PASS'
    if live_smoke and live_smoke.get('exit_code') == 0:
        real_api.append({'type':'platform_live_smoke','status':'PASS','command':live_smoke.get('command'),'exit_code':live_smoke.get('exit_code'),'stdout_tail':live_smoke.get('stdout_tail',''),'stderr_tail':live_smoke.get('stderr_tail',''),'required':True})
        final_status = 'PASS'
    else:
        real_api.append({'type':'platform_live_smoke_not_run','status':'NOT_RUN','required_for_full_pass':True,'reason':'live Platform runtime/quota/storage/wallet smoke requires approved lane and cleanup strategy; dry-run and route contracts verified in this pass'})
        blind_spots = ['live Platform shared capability smoke not run; requires safe tenant, internal secret, cleanup, and explicit lane approval','OpenAPI generation exists for internal APIs but public/internal full generated-client parity remains future work']
    return {
      'feature_id':'platform-shared-capability-contract-evidence',
      'change_scope':'platform-runtime-quota-storage-auth-wallet-contract-smoke-readiness',
      'affected_services':['platform-backend','ecommerce-backend','menu-backend','kyc-backend','platform-frontend'],
      'affected_routes':[item['route'] for routes in route_hits.values() for item in routes if not item['route'].startswith('internal.Use(')],
      'auth_context':{'public':'JWTAuth for admin/browser APIs','internal':'RequireInternalService via X-Internal-Service-Secret / HMAC-compatible internal boundary','live_smoke_requires':'approved local/dev/prod-candidate lane with non-prod safe tenant and internal secret'},
      'real_api_evidence':real_api,
      'browser_evidence':[],
      'contract_smoke_evidence':[{'type':'router_contract_routes','command':router_test['command'],'exit_code':router_test['exit_code'],'route_hits':route_hits},{'type':'platform_shared_capability_smoke_dry_run','command':dry_smoke.get('command'),'exit_code':dry_smoke.get('exit_code'),'stdout_tail':dry_smoke.get('stdout_tail',''),'prod_refusal_exit_code':dry_smoke.get('prod_refusal_exit_code'),'prod_refusal_stderr_tail':dry_smoke.get('prod_refusal_stderr_tail',''),'prod_url_refusal_exit_code':dry_smoke.get('prod_url_refusal_exit_code'),'prod_url_refusal_stderr_tail':dry_smoke.get('prod_url_refusal_stderr_tail','')}],
      'prod_dev_log_evidence':[],
      'negative_cases':[{'case':'missing_internal_route','expected':'bridge gate fails when required internal runtime/quota/storage/wallet route is absent'},{'case':'live_smoke_not_run','expected':'evidence remains PARTIAL_PASS and SelfCheck PASS_WITH_NOTES, never full PASS'}],
      'consumer_sweep':[{'consumer':'ecommerce/menu/kyc product backends','paths':['internal runtime jobs/callbacks','quota reservations','storage asset registry','wallet/metering settlement'],'enforced_by':'route inventory + dry-run smoke readiness; live consumer smoke pending approved lane'},{'consumer':'platform-frontend/admin console','paths':['JWT admin runtime/wallet/metering read APIs'],'enforced_by':'router route test + future browser gate'}],
      'risk_level':'high',
      'rollback_path':{'type':'git_revert_or_route_registration_restore','paths':['platform-backend/internal/router/router.go','platform-backend/tools/prod/platform-runtime-smoke.sh']},
      'blind_spots':blind_spots,
      'owner_role':'qa',
      'final_status':final_status
    }

def live_smoke_succeeded(evidence):
    for item in evidence.get('real_api_evidence') or []:
        if item.get('type') == 'platform_live_smoke_not_run' or item.get('status') == 'NOT_RUN':
            return False
        if item.get('exit_code') == 0:
            return True
    return False

def main():
    findings=[]
    if not PLATFORM.exists(): return result(VERIFIER,'FAIL',[{'severity':'error','message':'missing platform-backend','path':str(PLATFORM)}])
    router_test=run(['go','test','./internal/router','-run','TestPlatformSharedCapabilityContractRoutes'], PLATFORM, timeout=180)
    if router_test['exit_code']!=0: findings.append({'severity':'error','message':'go test ./internal/router -run TestPlatformSharedCapabilityContractRoutes failed','stderr_tail':router_test['stderr_tail']})
    route_hits, route_findings=router_routes(); findings.extend(route_findings)
    dry_smoke, smoke_findings=dry_runtime_smoke(); findings.extend(smoke_findings)
    live_smoke=None
    if os.environ.get('V_RUN_PLATFORM_SHARED_CAPABILITY_SMOKE','0') == '1':
        live_script=V_ROOT/'tools/contract-smoke/platform-shared-capability-smoke.sh'
        live_config=PLATFORM/'config.local.yaml'
        live_base=os.environ.get('PLATFORM_BASE_URL','http://127.0.0.1:8195')
        if live_script.exists() and live_config.exists() and re.match(r'^https?://(127\.0\.0\.1|localhost)(:\d+)?(/.*)?$', live_base):
            if os.environ.get('V_PLATFORM_SMOKE_ALLOW_WRITES') != '1' or os.environ.get('V_PLATFORM_SMOKE_CLEANUP_ACK') != '1':
                findings.append({'severity':'error','message':'V_RUN_PLATFORM_SHARED_CAPABILITY_SMOKE=1 requires explicit V_PLATFORM_SMOKE_ALLOW_WRITES=1 and V_PLATFORM_SMOKE_CLEANUP_ACK=1; gate must not auto-approve writes'})
            else:
                live_smoke=run([str(live_script),'--env','local','--execute','--base-url',live_base,'--config',str(live_config)], V_ROOT, timeout=120)
                if live_smoke.get('exit_code') != 0:
                    findings.append({'severity':'warning','message':'platform live readiness smoke attempted but failed; evidence remains partial','stderr_tail':live_smoke.get('stderr_tail',''),'stdout_tail':live_smoke.get('stdout_tail','')})
    evidence=build_evidence(route_hits, router_test, dry_smoke, live_smoke)
    REPORT_DIR.mkdir(parents=True,exist_ok=True); EVIDENCE_PATH.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    findings.extend([{**f,'path':str(EVIDENCE_PATH)} for f in validate_evidence_contract(evidence)])
    if evidence.get('final_status') in ('PASS','PASS_WITH_NOTES') and not live_smoke_succeeded(evidence):
        findings.append({'severity':'error','message':'PASS/PASS_WITH_NOTES Platform evidence requires successful live smoke; NOT_RUN must remain PARTIAL_PASS','path':str(EVIDENCE_PATH)})
    status='FAIL' if any(f.get('severity')=='error' for f in findings) else ('PASS' if evidence.get('final_status')=='PASS' else 'PASS_WITH_NOTES')
    return result(VERIFIER,status,findings,{'evidence_contract':str(EVIDENCE_PATH),'router_test':router_test,'runtime_smoke_dry_run':dry_smoke})
if __name__=='__main__': raise SystemExit(main())
