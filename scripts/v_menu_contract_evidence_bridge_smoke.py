#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys
from v_governance_gate_common import ROOT, V_ROOT, validate_evidence_contract

def emit_result(verifier, status, findings, extra=None):
    import json, time
    report_dir = V_ROOT / 'reports' / 'evidence-contract' / 'menu-studio-core-chain'
    report_dir.mkdir(parents=True, exist_ok=True)
    payload={'feature':'v-menu-contract-evidence-bridge','verifier':verifier,'status':status,'findings':findings,'extra':extra or {},'generated_at_epoch':time.time()}
    (report_dir / f'{verifier}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status in ('PASS','PASS_WITH_NOTES') else 1

def main():
    findings=[]
    good={'feature_id':'menu-fixture','change_scope':'menu-studio-core-chain','affected_services':['menu-backend','menu-frontend'],'affected_routes':['POST /api/v1/menu/studio/jobs'],'auth_context':{},'real_api_evidence':[{'status':'NOT_RUN','type':'menu_real_contract_smoke_not_run'}],'browser_evidence':[{'status':'NOT_RUN','required':'fixture'}],'contract_smoke_evidence':[{'status':'PARTIAL_PASS','type':'menu_swagger_route_inventory'}],'prod_dev_log_evidence':[{'status':'NOT_RUN','required_fields':['request_id','trace_id']}],'negative_cases':[{'case':'quota insufficient'}],'consumer_sweep':[{'consumer':'menu-frontend/src/services/studio.ts','status':'PASS'}],'risk_level':'high','rollback_path':{},'blind_spots':['fixture partial'],'owner_role':'qa','final_status':'PARTIAL_PASS'}
    if validate_evidence_contract(good): findings.append({'severity':'error','message':'valid Menu partial fixture failed validation'})
    bad=dict(good); bad['final_status']='PASS_WITH_NOTES'; bad['blind_spots']=[]
    bad_findings=validate_evidence_contract(bad)
    if not any('weak/unrun evidence' in f.get('message','') for f in bad_findings):
        findings.append({'severity':'error','message':'Menu false-confidence PASS_WITH_NOTES/NOT_RUN fixture was not rejected','actual':bad_findings})
    selector=subprocess.run([sys.executable,'scripts/v_business_gate_selector.py','--changed-file','menu-backend/docs/openapi/swagger.json','--changed-file','menu-frontend/src/services/studio.ts','--format','json'],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if selector.returncode!=0:
        findings.append({'severity':'error','message':'Menu bridge selector smoke failed','stderr':selector.stderr[-1000:]})
    else:
        payload=json.loads(selector.stdout); gates={g.get('feature') for g in payload.get('selected_gates',[])}
        if 'v-menu-contract-evidence-bridge' not in gates:
            findings.append({'severity':'error','message':'Menu bridge selector did not select v-menu-contract-evidence-bridge','payload':payload})
        bridge_gate=next((g for g in payload.get('selected_gates',[]) if g.get('feature')=='v-menu-contract-evidence-bridge'), {})
        command=bridge_gate.get('command','')
        if 'SELFCHECK_ALLOW_PARTIAL=1' not in command:
            findings.append({'severity':'error','message':'Menu bridge selector must allow bounded partial evidence because live write smoke is approval-gated','command':command})
    return emit_result('v-menu-contract-evidence-bridge-smoke','PASS' if not findings else 'FAIL',findings)
if __name__=='__main__': raise SystemExit(main())
