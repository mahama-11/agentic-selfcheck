#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, subprocess
from pathlib import Path

GOOD_FEATURE = '''id: good-production-frontend
project: agentic-selfcheck
description: Production C-risk frontend page implementation.
level_target: L3.5
repair_policy: default-repair-policy
depends_on: [review-gates]
must_pass:
  static:
    - frontend-design-quality-pack-gate
    - frontend-existing-product-intake-gate
    - frontend-prototype-foundation-ledger-gate
    - frontend-prototype-iteration-policy-gate
    - frontend-design-lane-generation-gate
    - frontend-high-fidelity-prototype-gate
    - frontend-prototype-freeze-gate
    - frontend-prototype-parity-gate
reviewer_gates: [architect, spec-review, quality-review, qa, final-verification]
human_required: [Human visual acceptance before implementation]
risk_dimensions: [frontend, visual-quality]
governance:
  frontend_route_policy: production-implementation
  risk_level: C
'''

BAD_FEATURE = '''id: bad-production-frontend
project: agentic-selfcheck
description: Production C-risk frontend page implementation missing prototype-first gates.
level_target: L3.5
repair_policy: default-repair-policy
depends_on: [review-gates]
must_pass:
  static:
    - frontend-high-fidelity-prototype-gate
reviewer_gates: [architect, spec-review, quality-review, qa, final-verification]
human_required: [Human visual acceptance before implementation]
risk_dimensions: [frontend, visual-quality]
governance:
  frontend_route_policy: production-implementation
  risk_level: C
'''

BAD_MISSING_RISK_FEATURE = '''id: bad-production-frontend-missing-risk
project: agentic-selfcheck
description: Production frontend page implementation with no explicit risk.
level_target: L3.5
repair_policy: default-repair-policy
depends_on: [review-gates]
must_pass:
  static: []
reviewer_gates: [architect, spec-review, quality-review, qa, final-verification]
human_required: [Human visual acceptance before implementation]
risk_dimensions: [frontend]
governance:
  frontend_route_policy: production-implementation
'''

BAD_MISSING_POLICY_FEATURE = '''id: bad-c-frontend-missing-policy
project: agentic-selfcheck
description: Production implementation of a C-risk frontend page, but no route policy was declared.
level_target: L3.5
repair_policy: default-repair-policy
depends_on: [review-gates]
must_pass:
  static: []
reviewer_gates: [architect, spec-review, quality-review, qa, final-verification]
human_required: [Human visual acceptance before implementation]
risk_dimensions: [frontend]
governance:
  risk_level: C
'''

B_FEATURE = '''id: low-risk-copy-frontend
project: agentic-selfcheck
description: B-risk copy-only frontend tweak.
level_target: L3
repair_policy: default-repair-policy
depends_on: [review-gates]
must_pass:
  static:
    - frontend-high-fidelity-prototype-gate
reviewer_gates: [spec-review, final-verification]
human_required: [Reviewer confirms copy-only scope]
risk_dimensions: [frontend]
governance:
  frontend_route_policy: low-risk-copy
  risk_level: B
'''

TASK_C = {
    'id': 'frontend-risk-routing-smoke-product-center-redesign',
    'title': 'Redesign ecommerce Product Center workbench page',
    'description': 'Complex frontend page redesign with new interaction flow and visual hierarchy.',
    'changed_files': ['ecommerce-frontend/src/pages/ProductCenter.tsx'],
}

TASK_B = {
    'id': 'button-copy',
    'title': 'Adjust button copy',
    'description': 'Small copy-only change in a React component.',
    'changed_files': ['ecommerce-frontend/src/components/Button.tsx'],
}

TASK_VUE_C = {
    'id': 'profile-view-redesign',
    'title': 'Redesign profile settings view',
    'description': 'Complex frontend view redesign with new interaction flow.',
    'changed_files': ['web/src/views/Profile.vue'],
}


def run(cmd: list[str], root: Path) -> tuple[bool, str, str, int]:
    cp=subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return cp.returncode == 0, cp.stdout, cp.stderr, cp.returncode


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json','text'], default='json')
    args=ap.parse_args()
    root=Path(args.root).resolve()
    smoke=root/'.hermes/workflows/frontend-risk-routing-smoke'
    if smoke.exists(): shutil.rmtree(smoke)
    smoke.mkdir(parents=True, exist_ok=True)
    good=smoke/'good.yaml'; good.write_text(GOOD_FEATURE, encoding='utf-8')
    bad=smoke/'bad.yaml'; bad.write_text(BAD_FEATURE, encoding='utf-8')
    bad_missing_risk=smoke/'bad-missing-risk.yaml'; bad_missing_risk.write_text(BAD_MISSING_RISK_FEATURE, encoding='utf-8')
    bad_missing_policy=smoke/'bad-missing-policy.yaml'; bad_missing_policy.write_text(BAD_MISSING_POLICY_FEATURE, encoding='utf-8')
    low=smoke/'low.yaml'; low.write_text(B_FEATURE, encoding='utf-8')
    task_c=smoke/'task-c.json'; task_c.write_text(json.dumps(TASK_C), encoding='utf-8')
    task_b=smoke/'task-b.json'; task_b.write_text(json.dumps(TASK_B), encoding='utf-8')
    task_vue=smoke/'task-vue.json'; task_vue.write_text(json.dumps(TASK_VUE_C), encoding='utf-8')
    outside=Path('/tmp/frontend-risk-routing-outside-task.json')
    outside.write_text(json.dumps(TASK_C), encoding='utf-8')

    expected_wf=root/'.hermes/workflows/frontend-risk-routing-smoke-product-center-redesign'
    if expected_wf.exists(): shutil.rmtree(expected_wf)
    symlink_task=smoke/'task-symlink.json'; symlink_task.write_text(json.dumps({**TASK_C, 'id':'frontend-risk-routing-symlink-reuse'}), encoding='utf-8')
    child_symlink_task=smoke/'task-child-symlink.json'; child_symlink_task.write_text(json.dumps({**TASK_C, 'id':'frontend-risk-routing-child-symlink-reuse'}), encoding='utf-8')
    backslash_task=smoke/'task-backslash-traversal.json'; backslash_task.write_text(json.dumps({**TASK_C, 'id':'frontend-risk-routing-backslash-traversal', 'project':'ecommerce-frontend', 'project_root':'ecommerce-frontend', 'changed_files':['..\\ecommerce-frontend\\src\\pages\\Evil.tsx']}), encoding='utf-8')
    legacy_task=smoke/'task-legacy-incomplete.json'; legacy_task.write_text(json.dumps({**TASK_C, 'id':'frontend-risk-routing-legacy-incomplete-reuse'}), encoding='utf-8')
    symlink_wf=root/'.hermes/workflows/frontend-risk-routing-symlink-reuse'
    if symlink_wf.exists() or symlink_wf.is_symlink():
        if symlink_wf.is_symlink(): symlink_wf.unlink()
        else: shutil.rmtree(symlink_wf)
    symlink_wf.symlink_to('/tmp')
    child_wf=root/'.hermes/workflows/frontend-risk-routing-child-symlink-reuse'
    if child_wf.exists(): shutil.rmtree(child_wf)
    child_wf.mkdir(parents=True, exist_ok=True)
    (child_wf/'FRONTEND_WORKFLOW_STATE.json').write_text('{}', encoding='utf-8')
    (child_wf/'FRONTEND_EVIDENCE_MANIFEST.json').write_text('{}', encoding='utf-8')
    (child_wf/'PROJECT_ADAPTER.yaml').write_text('name: ecommerce-frontend\nroot: ecommerce-frontend\n', encoding='utf-8')
    (child_wf/'evil-link').symlink_to('/tmp')
    legacy_wf=root/'.hermes/workflows/frontend-risk-routing-legacy-incomplete-reuse'
    if legacy_wf.exists(): shutil.rmtree(legacy_wf)
    legacy_wf.mkdir(parents=True, exist_ok=True)
    (legacy_wf/'FRONTEND_WORKFLOW_STATE.json').write_text('{}', encoding='utf-8')
    (legacy_wf/'FRONTEND_EVIDENCE_MANIFEST.json').write_text('{}', encoding='utf-8')
    (legacy_wf/'PROJECT_ADAPTER.yaml').write_text('name: ecommerce-frontend\nroot: ecommerce-frontend\n', encoding='utf-8')

    cases=[]; ok=True
    commands=[
        ('good-production-feature', True, ['scripts/frontend_risk_router.py','--root','.','--feature-file',str(good),'--format','json']),
        ('bad-production-feature-missing-gates', False, ['scripts/frontend_risk_router.py','--root','.','--feature-file',str(bad),'--format','json']),
        ('bad-production-feature-missing-risk', False, ['scripts/frontend_risk_router.py','--root','.','--feature-file',str(bad_missing_risk),'--format','json']),
        ('bad-c-feature-missing-route-policy', False, ['scripts/frontend_risk_router.py','--root','.','--feature-file',str(bad_missing_policy),'--format','json']),
        ('low-risk-feature-does-not-require-prototype-chain', True, ['scripts/frontend_risk_router.py','--root','.','--feature-file',str(low),'--format','json']),
        ('task-c-routes-to-prototype-first', True, ['scripts/frontend_risk_router.py','--root','.','--task-json',str(task_c),'--expect-risk','C','--format','json']),
        ('task-b-stays-lightweight', True, ['scripts/frontend_risk_router.py','--root','.','--task-json',str(task_b),'--expect-risk','B','--format','json']),
        ('task-vue-routes-to-prototype-first', True, ['scripts/frontend_risk_router.py','--root','.','--task-json',str(task_vue),'--expect-risk','C','--format','json']),
        ('bad-task-json-outside-root', False, ['scripts/frontend_risk_router.py','--root','.','--task-json',str(outside),'--format','json']),
        ('init-c-workflow', True, ['scripts/frontend_risk_router.py','--root','.','--task-json',str(task_c),'--init-workflow','--format','json']),
        ('bad-symlink-workflow-reuse', False, ['scripts/frontend_risk_router.py','--root','.','--task-json',str(symlink_task),'--init-workflow','--format','json']),
        ('bad-child-symlink-workflow-reuse', False, ['scripts/frontend_risk_router.py','--root','.','--task-json',str(child_symlink_task),'--init-workflow','--format','json']),
        ('bad-backslash-traversal-task', False, ['scripts/frontend_risk_router.py','--root','.','--task-json',str(backslash_task),'--init-workflow','--format','json']),
        ('bad-legacy-incomplete-workflow-reuse', False, ['scripts/frontend_risk_router.py','--root','.','--task-json',str(legacy_task),'--init-workflow','--format','json']),
    ]
    for name, should_pass, cmd in commands:
        passed, stdout, stderr, rc=run(cmd, root)
        if name == 'task-c-routes-to-prototype-first' and passed:
            try:
                payload=json.loads(stdout)
                route=payload['results'][0].get('route', [])
                if 'existing-product-intake' not in route or 'prototype-foundation-ledger' not in route or 'prototype-iteration-policy' not in route: passed=False
            except Exception:
                passed=False
        if passed != should_pass: ok=False
        cases.append({'case':name,'expected':'PASS' if should_pass else 'FAIL','actual':'PASS' if passed else 'FAIL','returncode':rc,'stdout':stdout[-1600:],'stderr':stderr[-1600:]})
    expected_wf=root/'.hermes/workflows/frontend-risk-routing-smoke-product-center-redesign'
    wf_ok=(expected_wf/'PROTOTYPE_COVERAGE.md').exists() and (expected_wf/'README.md').exists() and (expected_wf/'FRONTEND_WORKFLOW_STATE.json').exists() and (expected_wf/'FRONTEND_EVIDENCE_MANIFEST.json').exists() and (expected_wf/'PROJECT_ADAPTER.yaml').exists() and (expected_wf/'PROTOTYPE_FOUNDATION_LEDGER.md').exists() and (expected_wf/'PROTOTYPE_ITERATION_POLICY.md').exists()
    for cleanup in (symlink_wf, child_wf, legacy_wf):
        if cleanup.is_symlink(): cleanup.unlink()
        elif cleanup.exists(): shutil.rmtree(cleanup)
    if not wf_ok: ok=False
    cases.append({'case':'init-created-prototype-workflow','expected':'PASS','actual':'PASS' if wf_ok else 'FAIL','workflow':str(expected_wf)})
    result={'status':'PASS' if ok else 'FAIL','cases':cases}
    if args.format == 'json': print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('status=' + result['status'])
        for c in cases: print(f"{c['case']}: expected {c['expected']} actual {c['actual']}")
    return 0 if ok else 1

if __name__ == '__main__':
    raise SystemExit(main())
