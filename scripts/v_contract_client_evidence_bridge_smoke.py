#!/usr/bin/env python3
from __future__ import annotations
from v_governance_gate_common import result, validate_evidence_contract

def main():
    good={
        'feature_id':'fixture','change_scope':'ecommerce-v1-api-contract-generated-client-drift','affected_services':['ecommerce-frontend'],'affected_routes':['GET /api/v1/ecommerce/products'],'auth_context':{},'real_api_evidence':[{'type':'real_contract_smoke_not_run','status':'NOT_RUN'}], 'browser_evidence':[], 'contract_smoke_evidence':[{'type':'openapi_generated_client'}], 'prod_dev_log_evidence':[], 'negative_cases':[{'case':'generated_client_drift'}], 'consumer_sweep':[{'consumer':'generated client'}], 'risk_level':'high', 'rollback_path':{}, 'blind_spots':['real smoke skipped'], 'owner_role':'qa', 'final_status':'PARTIAL_PASS'
    }
    bad=dict(good); bad['contract_smoke_evidence']=[]; bad['consumer_sweep']=[]
    findings=[]
    if validate_evidence_contract(good): findings.append({'severity':'error','message':'good partial high-risk generated-client fixture should validate'})
    bad_findings=validate_evidence_contract(bad)
    for expected in ['contract_smoke_evidence','consumer_sweep']:
        if not any(expected in f.get('message','') for f in bad_findings):
            findings.append({'severity':'error','message':f'bad fixture did not fail {expected}','actual':bad_findings})
    return result('v-contract-client-evidence-bridge-smoke','PASS' if not findings else 'FAIL',findings)
if __name__=='__main__': raise SystemExit(main())
