#!/usr/bin/env python3
from __future__ import annotations
from v_governance_gate_common import result, validate_evidence_contract
from v_platform_contract_evidence_bridge_gate import live_smoke_succeeded

def main():
    good={'feature_id':'fixture','change_scope':'platform-runtime-quota-storage-auth-wallet-contract-smoke-readiness','affected_services':['platform-backend'],'affected_routes':['POST /internal/v1/runtime/jobs'],'auth_context':{},'real_api_evidence':[{'type':'platform_live_smoke_not_run','status':'NOT_RUN'}],'browser_evidence':[],'contract_smoke_evidence':[{'type':'router_contract_routes'}],'prod_dev_log_evidence':[],'negative_cases':[{'case':'live_smoke_not_run'}],'consumer_sweep':[{'consumer':'product backends'}],'risk_level':'high','rollback_path':{},'blind_spots':['live smoke skipped'],'owner_role':'qa','final_status':'PARTIAL_PASS'}
    bad=dict(good); bad['contract_smoke_evidence']=[]; bad['consumer_sweep']=[]
    findings=[]
    if validate_evidence_contract(good): findings.append({'severity':'error','message':'good Platform partial fixture should validate'})
    bad_findings=validate_evidence_contract(bad)
    for expected in ['contract_smoke_evidence','consumer_sweep']:
        if not any(expected in f.get('message','') for f in bad_findings): findings.append({'severity':'error','message':f'bad fixture did not fail {expected}','actual':bad_findings})
    bad_pass=dict(good); bad_pass['final_status']='PASS_WITH_NOTES'; bad_pass['blind_spots']=[]
    bad_pass_findings=validate_evidence_contract(bad_pass)
    if not any('weak/unrun evidence' in f.get('message','') for f in bad_pass_findings):
        findings.append({'severity':'error','message':'generic Evidence Contract validator did not reject NOT_RUN/PASS_WITH_NOTES false-confidence combination','actual':bad_pass_findings})
    if live_smoke_succeeded(bad_pass):
        findings.append({'severity':'error','message':'live smoke detector should not accept NOT_RUN evidence'})
    return result('v-platform-contract-evidence-bridge-smoke','PASS' if not findings else 'FAIL',findings)
if __name__=='__main__': raise SystemExit(main())
