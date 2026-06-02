#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import time
from v_governance_gate_common import V_ROOT,result,load_json

def main():
    findings=[]
    required=['v-ai-native-governance-foundation-smoke','v-evidence-contract-schema-gate','v-contract-client-generation-gate','v-genai-observability-baseline-gate','v-genai-security-eval-baseline-gate','v-release-cron-branch-hygiene-baseline-gate']
    base=V_ROOT/'reports/ai-native-governance-foundation'
    now=time.time()
    max_age_seconds=900
    run_epochs=[]
    for rid in required:
        p=base/f'{rid}.json'
        if not p.exists():
            findings.append({'severity':'error','message':'missing verifier report','path':str(p)})
            continue
        obj=load_json(p)
        if obj.get('feature') != 'v-ai-native-governance-foundation':
            findings.append({'severity':'error','message':'report feature mismatch','path':str(p),'feature':obj.get('feature')})
        if obj.get('verifier') != rid:
            findings.append({'severity':'error','message':'report verifier mismatch','path':str(p),'verifier':obj.get('verifier')})
        if obj.get('status') not in ['PASS','PASS_WITH_NOTES']:
            findings.append({'severity':'error','message':'verifier report not passing','path':str(p),'status':obj.get('status')})
        epoch=float(obj.get('generated_at_epoch') or 0)
        run_epochs.append(epoch)
        if epoch <= 0 or now - epoch > max_age_seconds:
            findings.append({'severity':'error','message':'stale or missing generated_at_epoch','path':str(p),'age_seconds':round(now-epoch,3) if epoch else None})
    if run_epochs and max(run_epochs)-min(run_epochs) > max_age_seconds:
        findings.append({'severity':'error','message':'reports were not generated in the same bounded run window','span_seconds':round(max(run_epochs)-min(run_epochs),3)})
    return result('v-ai-native-governance-foundation-evidence-gate','PASS' if not findings else 'FAIL',findings, {'required_reports':required,'max_age_seconds':max_age_seconds})
if __name__=='__main__': raise SystemExit(main())
