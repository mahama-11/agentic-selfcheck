#!/usr/bin/env python3
from __future__ import annotations
from v_governance_gate_common import ROOT,V_ROOT,result,read,require_terms

def main():
    findings=[]
    docs=[V_ROOT/'docs/governance/api-contract-client-generation-baseline.md', V_ROOT/'docs/REAL_RUNTIME_CONTRACT_QA.md']
    for d in docs:
        if not d.exists(): findings.append({'severity':'error','message':'missing doc','path':str(d)})
    if docs[0].exists():
        text=read(docs[0])
        terms=['backend OpenAPI / JSON schema source of truth','generated frontend/API client','CI drift check','real contract smoke','consumer-driven contract tests','runtime provider route/fallback','product create/read/list','image job create/list/read/callback','template center','studio upload','four-slot multi-image generation','history/library','provider failure / callback retry']
        findings += require_terms(text, terms, str(docs[0]))
        if 'Menu is skipped' in text or 'Menu is intentionally' in text:
            findings.append({'severity':'error','message':'Menu skip language remains in contract baseline','path':str(docs[0])})
    if docs[1].exists():
        findings += require_terms(read(docs[1]), ['v-contract-smoke ecommerce product-create','Frontend visible mutation flow','generated/validated contracts'], str(docs[1]))
    cfg=ROOT/'config/v-business-gate-selector.yaml'
    if cfg.exists():
        t=read(cfg)
        findings += require_terms(t, ['platform-api-contract-surfaces','ecommerce-api-contract-and-consumer-surfaces','producer-only closure','menu-backend/docs/openapi','menu-frontend/src/services'], str(cfg))
    else: findings.append({'severity':'error','message':'missing selector config','path':str(cfg)})
    return result('v-contract-client-generation-gate','PASS' if not findings else 'FAIL',findings)
if __name__=='__main__': raise SystemExit(main())
