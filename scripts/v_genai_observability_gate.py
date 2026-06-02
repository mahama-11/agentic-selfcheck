#!/usr/bin/env python3
from __future__ import annotations
from v_governance_gate_common import ROOT,V_ROOT,result,read,require_terms,load_json

def main():
    findings=[]
    doc=V_ROOT/'docs/governance/genai-observability-baseline.md'
    schema=V_ROOT/'docs/governance/genai-observability-trace-schema.json'
    if not doc.exists(): findings.append({'severity':'error','message':'missing doc','path':str(doc)})
    else:
        text=read(doc)
        terms=['trace_id','request_id','user_id','org_id','product_code','workflow_id','session_id','job_id','runtime_job_id','provider','model','task_type','capability','prompt_id','prompt_hash','prompt_version','tool_calls','function_calls','input_asset_ids','output_asset_ids','token_usage','cost_estimate','actual_cost','latency_by_stage','fallback_attempts','safety_filter_result','callback_status','quota_reservation_id','charge_session_id','Platform RuntimeJob','Ecommerce ImageJob','Menu Studio Job','Prompt Center snapshot','StorageAsset registry','Wallet/metering/charge session','SelfCheck evidence']
        findings += require_terms(text, terms, str(doc))
    if not schema.exists(): findings.append({'severity':'error','message':'missing trace schema artifact','path':str(schema)})
    else:
        try:
            obj=load_json(schema)
            for field in ['trace_id','runtime_job_id','provider','prompt_hash','charge_session_id']:
                if field not in obj.get('required_trace_fields',[]): findings.append({'severity':'error','message':f'trace schema missing {field}','path':str(schema)})
            if not any('Menu Studio Job' == x for x in obj.get('required_joins',[])):
                findings.append({'severity':'error','message':'trace schema missing Menu Studio join','path':str(schema)})
        except Exception as ex: findings.append({'severity':'error','message':f'invalid trace schema: {ex}','path':str(schema)})
    for e in (ROOT/'examples/v-evidence-contract').glob('*.json'):
        try: obj=load_json(e)
        except Exception as ex:
            findings.append({'severity':'error','message':f'invalid example json: {ex}','path':str(e)}); continue
        joined=' '.join([str(x) for x in obj.get('prod_dev_log_evidence',[])])
        for term in ['request_id','trace_id']:
            if term not in joined: findings.append({'severity':'error','message':f'example missing log field {term}','path':str(e)})
    return result('v-genai-observability-baseline-gate','PASS' if not findings else 'FAIL',findings)
if __name__=='__main__': raise SystemExit(main())
