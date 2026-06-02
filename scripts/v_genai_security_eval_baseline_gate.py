#!/usr/bin/env python3
from __future__ import annotations
from v_governance_gate_common import V_ROOT,result,read,require_terms,load_json

def main():
    findings=[]
    doc=V_ROOT/'docs/governance/genai-security-evaluation-baseline.md'
    cases=V_ROOT/'docs/governance/genai-eval-harness-cases.json'
    if not doc.exists(): findings.append({'severity':'error','message':'missing doc','path':str(doc)})
    else:
        text=read(doc)
        terms=['Prompt Injection','Sensitive Information Disclosure','Supply Chain','Data and Model Poisoning','Improper Output Handling','Excessive Agency','System Prompt Leakage','Vector and Embedding Weakness','Offline evaluation','Online evaluation','Code rules','LLM-as-judge','Human review','Pairwise','failure rate','fallback rate','low confidence rate','generation-to-download completion rate','Menu Template Center','four-slot multi-image generation']
        findings += require_terms(text, terms, str(doc))
        if 'Menu is skipped' in text: findings.append({'severity':'error','message':'Menu skip language remains in security/eval baseline','path':str(doc)})
    if not cases.exists(): findings.append({'severity':'error','message':'missing eval harness case registry','path':str(cases)})
    else:
        try:
            obj=load_json(cases)
            for risk in ['Prompt Injection','Sensitive Information Disclosure','Excessive Agency','System Prompt Leakage']:
                if risk not in obj.get('owasp_llm_risks',[]): findings.append({'severity':'error','message':f'missing OWASP risk {risk}','path':str(cases)})
            for case in ['Menu Studio upload','Menu four-slot multi-image generation','低质量图片 safe fallback']:
                if case not in obj.get('offline_dataset',[]): findings.append({'severity':'error','message':f'missing offline eval case {case}','path':str(cases)})
            for metric in ['failure rate','fallback rate','generation-to-download completion rate','per-workflow cost']:
                if metric not in obj.get('online_metrics',[]): findings.append({'severity':'error','message':f'missing online metric {metric}','path':str(cases)})
        except Exception as ex: findings.append({'severity':'error','message':f'invalid eval harness registry: {ex}','path':str(cases)})
    return result('v-genai-security-eval-baseline-gate','PASS' if not findings else 'FAIL',findings)
if __name__=='__main__': raise SystemExit(main())
