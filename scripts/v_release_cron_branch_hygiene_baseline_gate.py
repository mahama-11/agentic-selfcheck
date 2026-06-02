#!/usr/bin/env python3
from __future__ import annotations
from v_governance_gate_common import ROOT,V_ROOT,result,read,require_terms,load_json

def main():
    findings=[]
    doc=V_ROOT/'docs/governance/release-ring-cron-branch-hygiene-baseline.md'
    cron=V_ROOT/'docs/governance/watchdog-governance-registry.example.json'
    branch=V_ROOT/'docs/governance/workspace-branch-hygiene-policy.json'
    if not doc.exists(): findings.append({'severity':'error','message':'missing doc','path':str(doc)})
    else:
        terms=['local isolated worktree','cloud dev with evidence','staging/prod candidate','prod approve + promote','SILENT','AUTO_HEALED','NEEDS_REVIEW','ESCALATED','owner','purpose','expected silence condition','max frequency','evidence output path','last 7d noise rate','state.db','Feishu delivery error','lark-cli','upstream gone','main ahead N','dirty files','cwd and git sha','Menu changes are high risk']
        text=read(doc); findings += require_terms(text, terms, str(doc))
        if 'Menu is skipped' in text: findings.append({'severity':'error','message':'Menu skip language remains in release hygiene baseline','path':str(doc)})
    for p, keys in [(cron,['severity','required_cron_fields','current_cleanup_targets','capacity_policy']),(branch,['required_review_env_fields','rules','main_ahead_classifications'])]:
        if not p.exists(): findings.append({'severity':'error','message':'missing machine policy artifact','path':str(p)}); continue
        try:
            obj=load_json(p)
            for k in keys:
                if k not in obj: findings.append({'severity':'error','message':f'policy missing {k}','path':str(p)})
        except Exception as ex: findings.append({'severity':'error','message':f'invalid policy artifact: {ex}','path':str(p)})
    cfg=ROOT/'config/v-business-gate-selector.yaml'
    if cfg.exists(): findings += require_terms(read(cfg), ['ai-native-governance-foundation-surfaces','v-ai-native-governance-foundation'], str(cfg))
    return result('v-release-cron-branch-hygiene-baseline-gate','PASS' if not findings else 'FAIL',findings)
if __name__=='__main__': raise SystemExit(main())
