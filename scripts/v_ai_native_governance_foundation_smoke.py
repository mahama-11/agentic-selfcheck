#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path
from v_governance_gate_common import ROOT, result, validate_evidence_contract

def main():
    findings=[]
    good={
      'feature_id':'smoke','change_scope':'governance','affected_services':[],'affected_routes':[],'auth_context':{},'real_api_evidence':[],'browser_evidence':[],'contract_smoke_evidence':[],'prod_dev_log_evidence':[],'negative_cases':[],'consumer_sweep':[],'risk_level':'low','rollback_path':{},'blind_spots':['fixture'], 'owner_role':'qa','final_status':'PARTIAL_PASS'
    }
    bad=dict(good); bad.pop('feature_id'); bad['risk_level']='unknown'; bad['extra_field']='forbidden'; bad['affected_services']='not-array'; bad['browser_evidence']=[{'user_facing_copy':'The backend runtime provider is ready.'}]
    if validate_evidence_contract(good): findings.append({'severity':'error','message':'valid fixture failed validation'})
    bad_findings=validate_evidence_contract(bad)
    for expected in ['feature_id','risk_level','additional properties','affected_services','internal term']:
        if not any(expected in f.get('message','').lower() for f in bad_findings):
            findings.append({'severity':'error','message':f'invalid fixture did not fail expected condition: {expected}','actual':bad_findings})
    for rel in ['features/v-contract-client-evidence-bridge.yaml','features/v-platform-contract-evidence-bridge.yaml','features/v-ai-native-governance-foundation.yaml','config/v-business-gate-selector.yaml']:
        p=ROOT/rel
        if p.exists():
            txt=p.read_text(encoding='utf-8')
            for stale in ['Menu is intentionally skipped','Menu product implementation is intentionally skipped','skip_menu: true','skip_menu_product_flow: true']:
                if stale in txt:
                    findings.append({'severity':'error','message':f'stale Menu exclusion language remains: {stale}','path':str(p)})
    selector = subprocess.run([sys.executable, 'scripts/v_business_gate_selector.py', '--changed-file', '/root/work/v/docs/governance/v-evidence-contract.md', '--changed-file', '/root/work/agentic-selfcheck/scripts/v_evidence_contract_gate.py', '--format', 'json'], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if selector.returncode != 0:
        findings.append({'severity':'error','message':'selector smoke failed','stderr':selector.stderr[-1000:]})
    else:
        payload=json.loads(selector.stdout)
        gates={g.get('feature') for g in payload.get('selected_gates',[])}
        if 'v-ai-native-governance-foundation' not in gates:
            findings.append({'severity':'error','message':'selector did not map V/SelfCheck governance paths to foundation gate','payload':payload})
    menu_selector = subprocess.run([sys.executable, 'scripts/v_business_gate_selector.py', '--changed-file', 'menu-backend/internal/modules/templatecenter/service.go', '--changed-file', 'menu-frontend/src/store/studioStore.ts', '--format', 'json'], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if menu_selector.returncode != 0:
        findings.append({'severity':'error','message':'Menu selector smoke failed','stderr':menu_selector.stderr[-1000:]})
    else:
        payload=json.loads(menu_selector.stdout)
        gates={g.get('feature') for g in payload.get('selected_gates',[])}
        if 'v-ai-native-governance-foundation' not in gates:
            findings.append({'severity':'error','message':'Menu core files did not select foundation gate','payload':payload})
    return result('v-ai-native-governance-foundation-smoke','PASS' if not findings else 'FAIL',findings)
if __name__=='__main__': raise SystemExit(main())
