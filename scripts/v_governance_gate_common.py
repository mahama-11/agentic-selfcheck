#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, sys, time
from pathlib import Path
try:
    import jsonschema
except Exception:  # pragma: no cover - gate still runs with manual checks if dependency disappears
    jsonschema = None
ROOT = Path(__file__).resolve().parents[1]
V_ROOT = Path(os.environ.get('V_WORKSPACE_ROOT', '/root/work/v'))
REPORT_DIR = V_ROOT / 'reports' / 'ai-native-governance-foundation'
INTERNAL_COPY_TERMS = ['prompt_plan','prompt_id','ready','backend','runtime','provider','contract','blocker','callback internals','result asset callback']

def result(verifier, status, findings, extra=None):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload={'feature':'v-ai-native-governance-foundation','verifier':verifier,'status':status,'findings':findings,'extra':extra or {},'generated_at_epoch':time.time()}
    p=REPORT_DIR/f'{verifier}.json'; p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status in ('PASS','PASS_WITH_NOTES') else 1

def read(path):
    p=Path(path); return p.read_text(encoding='utf-8')

def require_terms(text, terms, where):
    return [{'severity':'error','message':f'missing term: {term}','where':where} for term in terms if term not in text]

def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def validate_evidence_contract(obj):
    schema_path = ROOT / 'schemas' / 'v-evidence-contract.schema.json'
    schema = load_json(schema_path) if schema_path.exists() else None
    findings=[]
    if schema and jsonschema is not None:
        validator = jsonschema.Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(obj), key=lambda e: list(e.path)):
            loc = '.'.join(str(p) for p in err.path) or '<root>'
            findings.append({'severity':'error','message':f'schema violation at {loc}: {err.message}'})
    required=['feature_id','change_scope','affected_services','affected_routes','auth_context','real_api_evidence','browser_evidence','contract_smoke_evidence','prod_dev_log_evidence','negative_cases','consumer_sweep','risk_level','rollback_path','blind_spots','owner_role','final_status']
    for k in required:
        if k not in obj:
            findings.append({'severity':'error','message':f'missing required field: {k}'})
    for k in ['affected_services','affected_routes','real_api_evidence','browser_evidence','contract_smoke_evidence','prod_dev_log_evidence','negative_cases','consumer_sweep','blind_spots']:
        if k in obj and not isinstance(obj[k], list):
            findings.append({'severity':'error','message':f'{k} must be an array'})
    if obj.get('risk_level') not in ['low','medium','high','critical']:
        findings.append({'severity':'error','message':'risk_level must be low/medium/high/critical'})
    if obj.get('final_status') not in ['PASS','PASS_WITH_NOTES','PARTIAL_PASS','BLOCKED','FAIL']:
        findings.append({'severity':'error','message':'final_status invalid'})
    if 'prod/dev log evidence' in obj:
        findings.append({'severity':'error','message':'use prod_dev_log_evidence JSON field, not prod/dev log evidence'})
    if obj.get('final_status')=='PASS' and obj.get('blind_spots'):
        findings.append({'severity':'error','message':'PASS cannot have blind_spots'})
    if obj.get('risk_level') in ['high','critical']:
        for k in ['real_api_evidence','contract_smoke_evidence','negative_cases','consumer_sweep']:
            if not obj.get(k):
                findings.append({'severity':'error','message':f'high/critical risk evidence must include non-empty {k}'})
    evidence_status_values={'PASS','PASS_WITH_NOTES','PARTIAL_PASS','NOT_RUN','BLOCKED','FAIL','REQUIRED','COVERED_BY_SCHEMA'}
    weak_statuses={'NOT_RUN','PENDING','REQUIRED','FAIL','BLOCKED'}
    for k in ['real_api_evidence','browser_evidence','contract_smoke_evidence','prod_dev_log_evidence']:
        for idx, entry in enumerate(obj.get(k,[]) or []):
            if not isinstance(entry, dict):
                findings.append({'severity':'error','message':f'{k}[{idx}] must be an object'})
                continue
            if 'status' in entry and str(entry.get('status')).upper() not in evidence_status_values:
                findings.append({'severity':'error','message':f'{k}[{idx}].status invalid: {entry.get("status")}'})
            if k in ['real_api_evidence','contract_smoke_evidence'] and not any(field in entry for field in ['status','command','report_path','path','type','kind']):
                findings.append({'severity':'error','message':f'{k}[{idx}] must include status, command, report_path/path, type, or kind'})
    if obj.get('final_status') in ['PASS','PASS_WITH_NOTES']:
        for k in ['real_api_evidence','contract_smoke_evidence','negative_cases','consumer_sweep']:
            if not obj.get(k):
                findings.append({'severity':'error','message':f'{obj.get("final_status")} requires non-empty {k}'})
        for k in ['real_api_evidence','browser_evidence','contract_smoke_evidence','prod_dev_log_evidence']:
            for idx, entry in enumerate(obj.get(k,[]) or []):
                if not isinstance(entry, dict):
                    continue
                status=str(entry.get('status','PASS' if entry.get('exit_code') == 0 or entry.get('command') or entry.get('path') or entry.get('report_path') else '')).upper()
                if status in weak_statuses:
                    findings.append({'severity':'error','message':f'{obj.get("final_status")} cannot include weak/unrun evidence {k}[{idx}].status={status}'})
                if entry.get('exit_code') not in (None, 0):
                    findings.append({'severity':'error','message':f'{obj.get("final_status")} cannot include failing {k}[{idx}].exit_code={entry.get("exit_code")}'})
        for entry in obj.get('real_api_evidence',[]) + obj.get('contract_smoke_evidence',[]) + obj.get('prod_dev_log_evidence',[]):
            if isinstance(entry, dict) and entry.get('report_path'):
                p=Path(str(entry['report_path']))
                if not p.exists():
                    findings.append({'severity':'error','message':f'report_path does not exist for passing evidence: {p}'})
    user_copy_keys = {'user_facing_summary','user_facing_copy','customer_copy','display_copy','ui_copy','frontend_copy'}
    def scan_user_copy(value, path='<root>'):
        if isinstance(value, dict):
            for key, nested in value.items():
                nested_path=f'{path}.{key}'
                if key in user_copy_keys and isinstance(nested, str):
                    low=nested.lower()
                    for term in INTERNAL_COPY_TERMS:
                        if term.lower() in low:
                            findings.append({'severity':'error','message':f'user-facing evidence copy leaks internal term: {term}','path':nested_path})
                scan_user_copy(nested, nested_path)
        elif isinstance(value, list):
            for idx, nested in enumerate(value):
                scan_user_copy(nested, f'{path}[{idx}]')
    scan_user_copy(obj)
    return findings
