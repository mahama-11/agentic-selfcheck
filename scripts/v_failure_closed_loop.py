#!/usr/bin/env python3
"""P0/P1 failure closed-loop controller for V/SelfCheck.

P0: classify verifier/watchdog failures into bounded repair dispatches.
P1: stop repeated blind patching by escalating repeated same-signature failures to
architecture review capsules.

This controller is intentionally control-plane only: it writes evidence and owner
assignments; it does not patch product implementation while acting as verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SELF_ROOT = Path('/root/work/agentic-selfcheck')
REPORT_DIR = Path('reports/v-failure-closed-loop')
LEDGER_REL = REPORT_DIR / 'ledger.json'
LATEST_REL = REPORT_DIR / 'latest.json'
DISPATCH_REL = Path('.hermes/dispatch/v-failure-closed-loop')
ESCALATION_REL = REPORT_DIR / 'architecture-escalations'
MAX_TAIL = 4000
ARCHITECTURE_ESCALATION_OBSERVATIONS = 3

SENSITIVE_TEXT_PATTERNS = [
    (re.compile(r'(?i)(Authorization\s*[:=]\s*Bearer\s+)[A-Za-z0-9._~+\-/=]{6,}'), r'\1[REDACTED]'),
    (re.compile(r'(?i)(Bearer\s+)[A-Za-z0-9._~+\-/=]{6,}'), r'\1[REDACTED]'),
    (re.compile(r'(?i)\b(api[_-]?key|secret|password|passwd|token|credential|jwt|authorization)(\s*[:=]\s*)([^\s\'"`]{3,}|[\'\"][^\'\"]{3,}[\'\"])'), r'\1\2[REDACTED]'),
    (re.compile(r'(?i)(postgres|mysql|redis|mongodb)://[^\s\'"`]+'), '[REDACTED]'),
    (re.compile(r'\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,}\b'), '[REDACTED]'),
    (re.compile(r'\bsk-[A-Za-z0-9_-]{20,}\b'), '[REDACTED]'),
]

OWNER_BY_BUCKET = {
    'missing_evidence': 'orchestrator',
    'missing_secret_or_permission': 'human',
    'runtime_unavailable': 'qa',
    'provider_contract_drift': 'backend-agent',
    'api_contract_drift': 'backend-agent',
    'frontend_contract_drift': 'frontend-agent',
    'verifier_contract': 'orchestrator',
    'implementation_bug': 'developer',
    'unknown_failure': 'developer',
    'architecture_escalation': 'architect',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def safe_segment(value: Any, fallback: str = 'unknown') -> str:
    text = str(value or fallback)
    text = re.sub(r'[^A-Za-z0-9_.-]+', '-', text).strip('.-')
    return text or fallback


def redact_sensitive_text(value: str) -> str:
    if not value:
        return value
    redacted = value
    for pattern, replacement in SENSITIVE_TEXT_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def sanitize_for_storage(value: Any) -> Any:
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if isinstance(value, list):
        return [sanitize_for_storage(v) for v in value]
    if isinstance(value, dict):
        return {str(k): sanitize_for_storage(v) for k, v in value.items()}
    return value


def tail_text(value: Any, limit: int = MAX_TAIL) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return redact_sensitive_text(value[-limit:])
    return redact_sensitive_text(json.dumps(value, ensure_ascii=False, sort_keys=True)[-limit:])


def classify_bucket(text: str, group: str, verifier: str, feature: str) -> tuple[str, str]:
    lower = text.lower()
    if 'missing required evidence' in lower or group == 'evidence' or 'strict-audit' in verifier:
        return 'missing_evidence', 'required evidence is absent or strict evidence audit failed'
    if any(tok in lower for tok in ['permission', 'unauthorized', 'forbidden', 'secret', 'token', 'credential', 'jwt']):
        return 'missing_secret_or_permission', 'secret, auth, permission, or human boundary is required'
    if any(tok in lower for tok in ['connection refused', 'timed out', 'timeout', 'service unavailable', 'econnrefused']):
        return 'runtime_unavailable', 'runtime dependency or service was unavailable'
    if any(tok in lower for tok in ['provider', 'capability', 'minimax', 'kimi', 'model', 'subject_reference', 'image_reference']):
        return 'provider_contract_drift', 'provider capability or payload contract appears drifted'
    if any(tok in lower for tok in ['schema', 'contract', 'unexpected field', 'invalid json', 'decode', 'unmarshal']):
        return 'api_contract_drift', 'API/schema/contract mismatch is likely'
    if any(tok in lower for tok in ['selector', 'route', 'dom', 'text not found', 'locator', 'playwright', 'browser']):
        return 'frontend_contract_drift', 'frontend route/browser contract likely changed'
    if any(tok in lower for tok in ['unsafe harness', 'harness not found', 'selected verifier groups contain no verifiers', 'unknown verifier', 'unknown feature']):
        return 'verifier_contract', 'SelfCheck verifier wiring or feature contract needs repair'
    if feature or verifier:
        return 'implementation_bug', 'bounded implementation or verifier failure needs owner repair'
    return 'unknown_failure', 'unclassified failure requires triage'


def stable_signature(parts: dict[str, Any]) -> str:
    basis = json.dumps(parts, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


def failure_from_loop(report: dict[str, Any], report_path: Path) -> list[dict[str, Any]]:
    feature = str(report.get('feature') or 'unknown-feature')
    out: list[dict[str, Any]] = []
    for f in report.get('failures') or []:
        group = str(f.get('group') or 'unknown')
        verifier = str(f.get('verifier') or 'unknown-verifier')
        status = str(f.get('status') or report.get('status') or 'FAIL')
        evidence = str(f.get('report_path') or report_path)
        text = '\n'.join([tail_text(f.get('reason')), tail_text(f), tail_text(report.get('stderr')), tail_text(report.get('stdout'))])
        bucket, reason = classify_bucket(text, group, verifier, feature)
        out.append({
            'source_kind': 'loop', 'feature': feature, 'group': group, 'verifier': verifier,
            'status': status, 'exit_code': f.get('exit_code'), 'evidence': evidence,
            'raw_reason': tail_text(f.get('reason')), 'bucket': bucket, 'classification_reason': reason,
            'text_tail': text[-MAX_TAIL:],
        })
    return out


def failure_from_trigger(trigger: dict[str, Any], report_path: Path, repo: str | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    selector = trigger.get('business_gate_selector') or {}
    executions = selector.get('executions') or []
    if executions:
        for ex in executions:
            status = str(ex.get('status') or ('FAIL' if ex.get('exit_code') not in (0, None) else 'PASS'))
            if status in {'PASS', 'PASS_WITH_NOTES'} and ex.get('exit_code') in (0, None):
                continue
            feature = str(ex.get('feature') or ex.get('gate') or 'unknown-feature')
            group = str(ex.get('groups') or ex.get('group') or 'business')
            verifier = str(ex.get('verifier') or 'business-gate')
            evidence = str(ex.get('report') or ex.get('loop_report') or report_path)
            text = '\n'.join([tail_text(ex), tail_text(trigger.get('stderr')), tail_text(trigger.get('raw_stdout'))])
            bucket, reason = classify_bucket(text, group, verifier, feature)
            out.append({'source_kind': 'trigger', 'repo': repo, 'feature': feature, 'group': group, 'verifier': verifier, 'status': status, 'exit_code': ex.get('exit_code'), 'evidence': evidence, 'bucket': bucket, 'classification_reason': reason, 'text_tail': text[-MAX_TAIL:]})
    for finding in selector.get('findings') or []:
        status = str(finding.get('status') or finding.get('severity') or 'FAIL')
        feature = str(finding.get('feature') or finding.get('gate') or 'business-gate-selector')
        group = str(finding.get('group') or 'business')
        verifier = str(finding.get('verifier') or finding.get('finding_id') or 'business-gate-finding')
        text = tail_text(finding)
        bucket, reason = classify_bucket(text, group, verifier, feature)
        out.append({'source_kind': 'business-gate-selector-finding', 'repo': repo, 'feature': feature, 'group': group, 'verifier': verifier, 'status': status, 'exit_code': finding.get('exit_code'), 'evidence': str(finding.get('evidence') or report_path), 'bucket': bucket, 'classification_reason': reason, 'text_tail': text[-MAX_TAIL:]})
    frontend_gate = trigger.get('frontend_implementation_gate') or {}
    if isinstance(frontend_gate, dict) and frontend_gate.get('status') in {'FAIL', 'BLOCKED'}:
        text = tail_text(frontend_gate)
        bucket, reason = classify_bucket(text, 'frontend', 'frontend-implementation-gate', 'frontend-implementation-hook')
        out.append({'source_kind': 'frontend-implementation-gate', 'repo': repo, 'feature': 'frontend-implementation-hook', 'group': 'frontend', 'verifier': 'frontend-implementation-gate', 'status': str(frontend_gate.get('status')), 'exit_code': frontend_gate.get('exit_code'), 'evidence': str(report_path), 'bucket': bucket, 'classification_reason': reason, 'text_tail': text[-MAX_TAIL:]})
    for event_result in trigger.get('events') or trigger.get('event_results') or []:
        if not isinstance(event_result, dict):
            continue
        if event_result.get('exit_code') in (0, None) and event_result.get('status') not in {'FAIL', 'BLOCKED'}:
            continue
        feature = str(event_result.get('feature') or event_result.get('event') or 'selfcheck-event')
        text = '\n'.join([tail_text(event_result), tail_text(event_result.get('stderr')), tail_text(event_result.get('stdout'))])
        bucket, reason = classify_bucket(text, 'event', 'selfcheck-event-trigger', feature)
        out.append({'source_kind': 'event-trigger', 'repo': repo, 'feature': feature, 'group': 'event', 'verifier': 'selfcheck-event-trigger', 'status': str(event_result.get('status') or 'FAIL'), 'exit_code': event_result.get('exit_code'), 'evidence': str(report_path), 'bucket': bucket, 'classification_reason': reason, 'text_tail': text[-MAX_TAIL:]})
    if not out and (trigger.get('exit_code') not in (0, None) or trigger.get('status') in {'FAIL', 'BLOCKED'}):
        feature = str(trigger.get('feature') or 'v-continuous-governance')
        text = '\n'.join([tail_text(trigger.get('stderr')), tail_text(trigger.get('raw_stdout')), tail_text(trigger)])
        bucket, reason = classify_bucket(text, 'governance', 'v-continuous-governance-trigger', feature)
        out.append({'source_kind': 'trigger', 'repo': repo, 'feature': feature, 'group': 'governance', 'verifier': 'v-continuous-governance-trigger', 'status': str(trigger.get('status') or 'FAIL'), 'exit_code': trigger.get('exit_code'), 'evidence': str(report_path), 'bucket': bucket, 'classification_reason': reason, 'text_tail': text[-MAX_TAIL:]})
    return out


def failure_from_watchdog(report: dict[str, Any], report_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for f in report.get('failures') or []:
        repo = str(f.get('repo') or '')
        trigger = f.get('trigger') or {}
        failures = failure_from_trigger(trigger, report_path, repo=repo)
        if not failures:
            gates = ','.join(str(x) for x in (f.get('selected_gates') or [])) or 'unknown-feature'
            text = '\n'.join([tail_text(f), tail_text(trigger.get('stderr')), tail_text(trigger.get('raw_stdout'))])
            bucket, reason = classify_bucket(text, 'watchdog', 'working-tree-business-gate', gates)
            failures.append({'source_kind': 'watchdog', 'repo': repo, 'feature': gates, 'group': 'watchdog', 'verifier': 'working-tree-business-gate', 'status': str(f.get('status') or 'FAIL'), 'exit_code': trigger.get('exit_code'), 'evidence': str(report_path), 'bucket': bucket, 'classification_reason': reason, 'text_tail': text[-MAX_TAIL:]})
        out.extend(failures)
    return out


def extract_failures(report: dict[str, Any], report_path: Path) -> list[dict[str, Any]]:
    if isinstance(report.get('failures'), list) and report.get('feature'):
        return failure_from_loop(report, report_path)
    if isinstance(report.get('failures'), list) and report.get('source') == 'v_working_tree_governance_watchdog.py':
        return failure_from_watchdog(report, report_path)
    if report.get('business_gate_selector') or report.get('events') or report.get('event_results') or report.get('frontend_implementation_gate'):
        return failure_from_trigger(report, report_path)
    # Fallback for minimal synthetic or external reports.
    if report.get('status') in {'FAIL', 'BLOCKED', 'NEEDS_REPAIR'} or report.get('exit_code') not in (0, None):
        feature = str(report.get('feature') or 'unknown-feature')
        group = str(report.get('group') or 'unknown')
        verifier = str(report.get('verifier') or 'unknown-verifier')
        text = tail_text(report)
        bucket, reason = classify_bucket(text, group, verifier, feature)
        return [{'source_kind': 'generic', 'feature': feature, 'group': group, 'verifier': verifier, 'status': str(report.get('status') or 'FAIL'), 'exit_code': report.get('exit_code'), 'evidence': str(report_path), 'bucket': bucket, 'classification_reason': reason, 'text_tail': text[-MAX_TAIL:]}]
    return []


def incident_id_for(failure: dict[str, Any]) -> tuple[str, str]:
    sig_basis = {
        'feature': failure.get('feature'),
        'group': failure.get('group'),
        'verifier': failure.get('verifier'),
        'bucket': failure.get('bucket'),
        'repo': failure.get('repo'),
        # Deliberately exclude volatile evidence path/timestamp; repeated same symptom should aggregate.
    }
    sig = stable_signature(sig_basis)
    feature = safe_segment(failure.get('feature'), 'feature')[:48]
    bucket = safe_segment(failure.get('bucket'), 'bucket')[:32]
    return f'{feature}-{bucket}-{sig}', sig


def render_dispatch(incident: dict[str, Any]) -> str:
    latest = incident.get('latest_failure') or {}
    groups = latest.get('group') or '<affected-groups>'
    feature = latest.get('feature') or '<feature>'
    return f"""# Repair Assignment: {incident['incident_id']}

Owner: {incident['owner']}
Status: {incident['status']}
Bucket: {incident['bucket']}
Observations: {incident['observations']}
Feature: `{feature}`
Group: `{groups}`
Verifier: `{latest.get('verifier')}`
Repo: `{latest.get('repo') or ''}`
Evidence: `{latest.get('evidence')}`

## Classification

{latest.get('classification_reason')}

## Required behavior

- Investigate root cause before patching.
- Do not remove or weaken the failing verifier/gate to make the report green.
- Fix only inside the assigned owner lane; SelfCheck remains verifier/control-plane.
- After repair, rerun the affected SelfCheck loop or business gate.
- If this incident reaches architecture escalation, stop blind patching and review module/interface/seam.

## Suggested rerun

```bash
cd /root/work/agentic-selfcheck
python3 -m selfcheck loop --root . --feature {feature} --groups {groups} --strict-audit --timeout 300
```

## Failure tail

```text
{latest.get('text_tail', '')[-3000:]}
```
"""


def render_escalation(incident: dict[str, Any]) -> str:
    latest = incident.get('latest_failure') or {}
    return f"""# Architecture Escalation: {incident['incident_id']}

Status: ESCALATE_ARCHITECTURE
Bucket: {incident['bucket']}
Owner: architect
Observations: {incident['observations']}
First seen: {incident.get('first_seen_at')}
Last seen: {incident.get('last_seen_at')}
Feature: `{latest.get('feature')}`
Group: `{latest.get('group')}`
Verifier: `{latest.get('verifier')}`
Repo: `{latest.get('repo') or ''}`
Evidence: `{latest.get('evidence')}`

## Why this escalated

The same failure signature crossed the bounded repair threshold ({ARCHITECTURE_ESCALATION_OBSERVATIONS} observations). Stop repeated patching and inspect the relevant module/interface/seam before continuing implementation repairs.

## Architecture review prompt

- Which module/interface/seam is too shallow or leaking?
- Which caller knowledge should be hidden behind a deeper interface?
- Which invariant should become a contract or verifier?
- What regression test proves this failure family cannot escape again?
- What is the smallest refactor that increases locality without broad churn?

## Latest failure tail

```text
{latest.get('text_tail', '')[-3000:]}
```
"""


def update_ledger(root: Path, failures: list[dict[str, Any]], report_path: Path, source: str) -> dict[str, Any]:
    ledger_path = root / LEDGER_REL
    ledger = load_json(ledger_path, {'version': 1, 'incidents': []})
    by_id = {i.get('incident_id'): i for i in ledger.get('incidents', []) if i.get('incident_id')}
    ts = now_iso()
    updated: list[dict[str, Any]] = []
    dispatches: list[str] = []
    escalations: list[str] = []

    report_display = redact_sensitive_text(str(report_path))
    source_display = redact_sensitive_text(str(source))
    for failure in failures:
        failure = sanitize_for_storage(failure)
        incident_id, sig = incident_id_for(failure)
        incident = by_id.get(incident_id)
        if not incident:
            incident = {
                'incident_id': incident_id,
                'signature': sig,
                'first_seen_at': ts,
                'observations': 0,
                'events': [],
            }
            by_id[incident_id] = incident
        incident['last_seen_at'] = ts
        incident['observations'] = int(incident.get('observations') or 0) + 1
        incident['bucket'] = failure.get('bucket')
        incident['owner'] = OWNER_BY_BUCKET.get(str(failure.get('bucket')), 'developer')
        incident['latest_failure'] = failure
        incident.setdefault('evidence_reports', [])
        if report_display not in incident['evidence_reports']:
            incident['evidence_reports'].append(report_display)
        incident.setdefault('events', []).append({'ts': ts, 'event': 'observed_failure', 'source': source_display, 'bucket': failure.get('bucket'), 'evidence': report_display})
        if len(incident['events']) > 50:
            incident['events'] = incident['events'][-50:]

        if incident['owner'] == 'human':
            incident['status'] = 'NEEDS_HUMAN'
            incident['next_action'] = 'human_boundary_decision'
        elif int(incident['observations']) >= ARCHITECTURE_ESCALATION_OBSERVATIONS or failure.get('bucket') == 'architecture_escalation':
            incident['status'] = 'ESCALATE_ARCHITECTURE'
            incident['owner'] = 'architect'
            incident['next_action'] = 'architecture_review_before_more_patch_repairs'
            path = root / ESCALATION_REL / f'{incident_id}.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_escalation(incident), encoding='utf-8')
            incident['architecture_escalation'] = str(path)
            escalations.append(str(path))
        else:
            incident['status'] = 'NEEDS_REPAIR'
            incident['next_action'] = 'dispatch_owner_repair_then_rerun_gate'
            path = root / DISPATCH_REL / f'{incident_id}.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render_dispatch(incident), encoding='utf-8')
            incident['dispatch'] = str(path)
            dispatches.append(str(path))
        updated.append(incident)

    incidents = sorted(by_id.values(), key=lambda i: (str(i.get('status')), str(i.get('bucket')), str(i.get('incident_id'))))
    summary: dict[str, Any] = {'total': len(incidents), 'by_status': {}, 'by_bucket': {}, 'active': 0, 'architecture_escalations': 0}
    for incident in incidents:
        status = str(incident.get('status') or 'UNKNOWN')
        bucket = str(incident.get('bucket') or 'unknown')
        summary['by_status'][status] = summary['by_status'].get(status, 0) + 1
        summary['by_bucket'][bucket] = summary['by_bucket'].get(bucket, 0) + 1
        if status not in {'RESOLVED', 'ACCEPTED_RISK', 'FALSE_POSITIVE'}:
            summary['active'] += 1
        if status == 'ESCALATE_ARCHITECTURE':
            summary['architecture_escalations'] += 1
    ledger = {'version': 1, 'generated_at': ts, 'policy': {'architecture_escalation_observations': ARCHITECTURE_ESCALATION_OBSERVATIONS, 'contract': 'P0 classify/dispatch; P1 repeated same-signature failures escalate to architecture review.'}, 'summary': summary, 'incidents': incidents}
    write_json(ledger_path, ledger)
    latest = {'status': 'PASS' if not failures else ('ESCALATE_ARCHITECTURE' if escalations else 'NEEDS_REPAIR'), 'generated_at': ts, 'source': source_display, 'report': report_display, 'failure_count': len(failures), 'updated_incidents': [i.get('incident_id') for i in updated], 'dispatches': dispatches, 'architecture_escalations': escalations, 'ledger': str(ledger_path), 'summary': summary}
    write_json(root / LATEST_REL, latest)
    return latest


def ingest(root: Path, report_path: Path, source: str) -> dict[str, Any]:
    report = load_json(report_path, None)
    if not isinstance(report, dict):
        raise SystemExit(f'report is not a JSON object: {report_path}')
    failures = extract_failures(report, report_path)
    return update_ledger(root, failures, report_path, source)


def status(root: Path) -> dict[str, Any]:
    ledger = load_json(root / LEDGER_REL, {'version': 1, 'incidents': []})
    return {'ledger': str(root / LEDGER_REL), 'summary': ledger.get('summary') or {'total': 0}, 'latest': str(root / LATEST_REL)}


def main() -> int:
    ap = argparse.ArgumentParser(description='Classify SelfCheck failures and dispatch/escalate bounded repair loops.')
    ap.add_argument('action', choices=['ingest', 'status'])
    ap.add_argument('--root', default=str(SELF_ROOT))
    ap.add_argument('--report')
    ap.add_argument('--source', default='manual')
    ap.add_argument('--format', choices=['json', 'text'], default='text')
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if args.action == 'ingest':
        if not args.report:
            raise SystemExit('--report is required for ingest')
        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = (root / report_path).resolve()
        result = ingest(root, report_path, args.source)
    else:
        result = status(root)

    if args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result.get('status') in {'NEEDS_REPAIR', 'ESCALATE_ARCHITECTURE'}:
            print(f"{result['status']}: failures={result.get('failure_count')} ledger={result.get('ledger')}")
            for p in result.get('dispatches') or []:
                print(f'DISPATCH: {p}')
            for p in result.get('architecture_escalations') or []:
                print(f'ESCALATE: {p}')
        elif args.action == 'status':
            print(json.dumps(result.get('summary'), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
