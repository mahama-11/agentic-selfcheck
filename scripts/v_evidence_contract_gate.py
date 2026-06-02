#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
from v_governance_gate_common import ROOT, V_ROOT, result, read, require_terms, load_json, validate_evidence_contract

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--format', default='json'); ap.parse_args()
    findings=[]
    doc=V_ROOT/'docs/governance/v-evidence-contract.md'
    schema=ROOT/'schemas/v-evidence-contract.schema.json'
    examples=sorted((ROOT/'examples/v-evidence-contract').glob('*.json'))
    required_examples={'ecommerce-v1-sellable-closure.example.json','platform-runtime-billing-auth-storage.example.json','menu-studio-core-chain.example.json'}
    for p in [doc,schema]:
        if not p.exists(): findings.append({'severity':'error','message':'missing file','path':str(p)})
    if required_examples - {p.name for p in examples}:
        findings.append({'severity':'error','message':'missing required product evidence examples','missing':sorted(required_examples-{p.name for p in examples})})
    if doc.exists():
        text=read(doc)
        findings += require_terms(text, ['feature_id','change_scope','affected_services','affected_routes','auth_context','real_api_evidence','browser_evidence','contract_smoke_evidence','prod_dev_log_evidence','negative_cases','consumer_sweep','risk_level','rollback_path','blind_spots','owner_role','final_status','Ecommerce V1 sellable closure','Menu Studio core chain','Platform shared capabilities'], str(doc))
        for stale in ['Menu is intentionally excluded','Menu Studio is explicitly skipped','首批跳过 Menu']:
            if stale in text:
                findings.append({'severity':'error','message':f'stale Menu exclusion remains: {stale}','path':str(doc)})
    if schema.exists():
        s=load_json(schema)
        for k in ['required','properties','additionalProperties']:
            if k not in s: findings.append({'severity':'error','message':f'schema missing {k}','path':str(schema)})
    for e in examples:
        try:
            obj=load_json(e); fs=validate_evidence_contract(obj)
            findings += [{**f,'path':str(e)} for f in fs]
        except Exception as ex:
            findings.append({'severity':'error','message':f'invalid example json: {ex}','path':str(e)})
    status='PASS' if not findings else 'FAIL'
    return result('v-evidence-contract-schema-gate', status, findings, {'examples':[str(p) for p in examples]})
if __name__=='__main__': raise SystemExit(main())
