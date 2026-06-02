#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

DEFAULT_BACKEND = Path('/root/work/v-worktrees/crossplanet-listing-strategy-backend')
DEFAULT_FRONTEND = Path('/root/work/v-worktrees/crossplanet-listing-strategy-frontend')

BACKEND_FOCUSED_TEST_CMD = [
    'go',
    'test',
    './internal/modules/productcore',
    '-run',
    'Test(BatchListingCreateAndAdopt|BatchListingPreviewAndValidation|UpdateListingVersion|CreateExportTaskSnapshotsAssetsAndListing|ExportTaskMaterializesListingDeliverableFormats)$',
]
FRONTEND_TYPECHECK_CMD = ['npm', 'run', 'typecheck']
FRONTEND_BUILD_CMD = ['npm', 'run', 'build']

# Durable assertions expected in the focused backend tests. These are intentionally
# behavior-level checks (persisted strategy input, status transitions, immutable
# historical versions, materialized export formats), not browser/internal-copy checks.
BACKEND_ASSERTION_TOKENS = {
    'strategy_input_persisted_in_response': 'expected listing strategy input to be persisted in response',
    'ready_status_after_adopt': 'listing status after adopt',
    'preview_does_not_persist_listing_versions': 'preview should not persist listing versions',
    'edited_strategy_input_round_trip': 'expected edited version to include strategy input',
    'historical_listing_version_immutable': 'historical listing version was mutated',
    'materialized_listing_deliverable_formats': 'TestExportTaskMaterializesListingDeliverableFormats',
}


def emit(payload: dict[str, Any], fmt: str) -> None:
    if fmt == 'json':
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    print(f"status={payload['status']} merge_state={payload['merge_state']} findings={len(payload['findings'])}")
    for item in payload['checks']:
        print(f"{item['status']} {item['name']} root={item.get('root', '-')}")
    for finding in payload['findings']:
        print(f"{finding['severity']} {finding['code']} {finding.get('path', '')}: {finding['message']}")


def finding(severity: str, code: str, message: str, path: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {'severity': severity, 'code': code, 'message': message}
    if path:
        payload['path'] = path
    return payload


def root_check(name: str, root: Path, required_file: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    check = {'name': name, 'root': str(root), 'required_file': required_file, 'status': 'PASS'}
    findings: list[dict[str, Any]] = []
    if not root.exists():
        check['status'] = 'FAIL'
        findings.append(finding('error', f'{name.upper()}_ROOT_MISSING', f'{name} root does not exist', str(root)))
    elif not (root / required_file).is_file():
        check['status'] = 'FAIL'
        findings.append(
            finding('error', f'{name.upper()}_ROOT_INVALID', f'{name} root is missing {required_file}', str(root))
        )
    return check, findings


def run_command(name: str, root: Path, cmd: list[str], timeout: int) -> dict[str, Any]:
    started = time.time()
    env = os.environ.copy()
    env.setdefault('CI', '1')
    try:
        proc = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            env=env,
        )
        output = proc.stdout
        status = 'PASS' if proc.returncode == 0 else 'FAIL'
        return {
            'name': name,
            'root': str(root),
            'command': cmd,
            'timeout_seconds': timeout,
            'duration_seconds': round(time.time() - started, 3),
            'exit_code': proc.returncode,
            'status': status,
            'output_tail': '\n'.join(output.splitlines()[-80:]),
        }
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ''
        if isinstance(output, bytes):
            output = output.decode(errors='replace')
        return {
            'name': name,
            'root': str(root),
            'command': cmd,
            'timeout_seconds': timeout,
            'duration_seconds': round(time.time() - started, 3),
            'exit_code': None,
            'status': 'FAIL',
            'output_tail': '\n'.join(str(output).splitlines()[-80:]),
            'timeout': True,
        }


def verify_backend_static_assertions(backend: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    test_path = backend / 'internal/modules/productcore/handler_test.go'
    check: dict[str, Any] = {
        'name': 'backend_durable_behavior_assertions',
        'root': str(backend),
        'path': str(test_path),
        'status': 'PASS',
        'assertions': sorted(BACKEND_ASSERTION_TOKENS),
    }
    findings: list[dict[str, Any]] = []
    try:
        text = test_path.read_text(encoding='utf-8')
    except OSError as exc:
        check['status'] = 'FAIL'
        findings.append(finding('error', 'BACKEND_TEST_FILE_UNREADABLE', str(exc), str(test_path)))
        return check, findings
    missing = [name for name, token in BACKEND_ASSERTION_TOKENS.items() if token not in text]
    if missing:
        check['status'] = 'FAIL'
        check['missing_assertions'] = missing
        findings.append(
            finding(
                'error',
                'BACKEND_DURABLE_ASSERTIONS_MISSING',
                'focused backend tests are missing durable behavior assertions: ' + ', '.join(missing),
                str(test_path),
            )
        )
    return check, findings


def verify_frontend_build_contract(frontend: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pkg = frontend / 'package.json'
    check: dict[str, Any] = {'name': 'frontend_typecheck_build_contract', 'root': str(frontend), 'path': str(pkg), 'status': 'PASS'}
    findings: list[dict[str, Any]] = []
    try:
        package = json.loads(pkg.read_text(encoding='utf-8'))
    except Exception as exc:  # noqa: BLE001 - diagnostic verifier should report exact failure.
        check['status'] = 'FAIL'
        findings.append(finding('error', 'FRONTEND_PACKAGE_UNREADABLE', str(exc), str(pkg)))
        return check, findings
    scripts = package.get('scripts') or {}
    expected = {'typecheck': 'tsc --noEmit', 'build': 'tsc -b && vite build'}
    missing_or_changed = {name: expected_cmd for name, expected_cmd in expected.items() if scripts.get(name) != expected_cmd}
    check['expected_scripts'] = expected
    if missing_or_changed:
        check['status'] = 'FAIL'
        check['actual_scripts'] = {name: scripts.get(name) for name in expected}
        findings.append(
            finding(
                'error',
                'FRONTEND_TYPECHECK_BUILD_CONTRACT_CHANGED',
                'frontend must expose stable typecheck/build scripts for same-run gate evidence',
                str(pkg),
            )
        )
    return check, findings


def classify_generated_evidence(checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'same_run_generated': [
            {
                'name': check['name'],
                'root': check.get('root'),
                'command': check.get('command'),
                'exit_code': check.get('exit_code'),
                'status': check.get('status'),
                'duration_seconds': check.get('duration_seconds'),
            }
            for check in checks
            if 'command' in check
        ],
        'governance_required': [
            'features/crossplanet-listing-strategy-gate-repair.yaml',
            'verifiers/crossplanet-listing-strategy-gate-repair-static.yaml',
            'scripts/crossplanet_gate_repair_quarantine.py',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Root-aware same-run CrossPlanet/List Strategy gate repair verifier.'
    )
    parser.add_argument('--selfcheck-root', default='.', help='agentic-selfcheck repository root')
    parser.add_argument('--backend-root', default=str(DEFAULT_BACKEND), help='CrossPlanet backend worktree root')
    parser.add_argument('--frontend-root', default=str(DEFAULT_FRONTEND), help='CrossPlanet frontend worktree root')
    parser.add_argument('--backend-timeout', type=int, default=120)
    parser.add_argument('--frontend-typecheck-timeout', type=int, default=90)
    parser.add_argument('--frontend-build-timeout', type=int, default=120)
    parser.add_argument('--format', choices=['json', 'text'], default='json')
    args = parser.parse_args()

    selfcheck_root = Path(args.selfcheck_root).resolve()
    backend = Path(args.backend_root).resolve()
    frontend = Path(args.frontend_root).resolve()

    checks: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    selfcheck, selfcheck_findings = root_check('selfcheck', selfcheck_root, 'features/crossplanet-listing-strategy-gate-repair.yaml')
    backend_root, backend_root_findings = root_check('backend', backend, 'go.mod')
    frontend_root, frontend_root_findings = root_check('frontend', frontend, 'package.json')
    checks.extend([selfcheck, backend_root, frontend_root])
    findings.extend(selfcheck_findings + backend_root_findings + frontend_root_findings)

    if backend_root['status'] == 'PASS':
        assertion_check, assertion_findings = verify_backend_static_assertions(backend)
        checks.append(assertion_check)
        findings.extend(assertion_findings)
        if assertion_check['status'] == 'PASS':
            backend_run = run_command('backend_focused_listing_strategy_tests', backend, BACKEND_FOCUSED_TEST_CMD, args.backend_timeout)
            checks.append(backend_run)
            if backend_run['status'] != 'PASS':
                findings.append(
                    finding(
                        'error',
                        'BACKEND_FOCUSED_TESTS_FAILED',
                        'backend focused listing-strategy tests failed in the declared backend root',
                        str(backend),
                    )
                )
            elif not re.search(r'ok\s+ecommerce-service/internal/modules/productcore', backend_run.get('output_tail', '')):
                findings.append(
                    finding(
                        'error',
                        'BACKEND_TEST_OUTPUT_NOT_RECOGNIZED',
                        'backend focused test output did not contain expected package pass line',
                        str(backend),
                    )
                )
                backend_run['status'] = 'FAIL'

    if frontend_root['status'] == 'PASS':
        frontend_contract, frontend_contract_findings = verify_frontend_build_contract(frontend)
        checks.append(frontend_contract)
        findings.extend(frontend_contract_findings)
        if frontend_contract['status'] == 'PASS':
            typecheck_run = run_command('frontend_typecheck', frontend, FRONTEND_TYPECHECK_CMD, args.frontend_typecheck_timeout)
            checks.append(typecheck_run)
            if typecheck_run['status'] != 'PASS':
                findings.append(
                    finding('error', 'FRONTEND_TYPECHECK_FAILED', 'frontend typecheck failed in the declared frontend root', str(frontend))
                )
            build_run = run_command('frontend_build', frontend, FRONTEND_BUILD_CMD, args.frontend_build_timeout)
            checks.append(build_run)
            if build_run['status'] != 'PASS':
                findings.append(
                    finding('error', 'FRONTEND_BUILD_FAILED', 'frontend build failed in the declared frontend root', str(frontend))
                )

    status = 'PASS' if not any(item.get('status') == 'FAIL' for item in checks) and not findings else 'FAIL'
    payload: dict[str, Any] = {
        'status': status,
        'merge_state': 'REPAIRED_GATES_PASS_SAME_RUN' if status == 'PASS' else 'REPAIR_REQUIRED',
        'scope': 'crossplanet-listing-strategy-gate-repair',
        'roots': {'selfcheck': str(selfcheck_root), 'backend': str(backend), 'frontend': str(frontend)},
        'checks': checks,
        'evidence': classify_generated_evidence(checks),
        'findings': findings,
        'hitl': [
            'Human approval is still required before merging or deploying CrossPlanet product worktrees.'
        ],
    }
    emit(payload, args.format)
    return 0 if status == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
