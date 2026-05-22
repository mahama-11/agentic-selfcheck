#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path

SELF_ROOT = Path('/root/work/agentic-selfcheck')
V_ROOT = Path('/root/work/v')
DOC_SUFFIXES = {'.md', '.mdx', '.rst'}
CODE_SUFFIXES = {'.py', '.go', '.ts', '.tsx', '.js', '.jsx', '.json', '.yaml', '.yml', '.toml', '.mod', '.sum'}
FRONTEND_SUFFIXES = {'.ts', '.tsx', '.js', '.jsx', '.vue', '.svelte', '.html', '.css', '.scss'}
FRONTEND_PATH_PARTS = {'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend', 'src/pages', 'src/components', 'src/views', 'app/routes', 'routes', 'templates'}


def norm(p: str) -> str:
    return p.strip().replace('\\', '/').removeprefix('./')


def unsafe_changed_path(p: str) -> bool:
    p = p.strip().replace('\\', '/')
    if not p or p.startswith('/'):
        return True
    return any(part in {'..', ''} for part in p.split('/'))


def events_for_path(p: str) -> set[str]:
    p = norm(p)
    suffix = Path(p).suffix.lower()
    name = Path(p).name
    events: set[str] = set()
    if p.startswith(('docs/', 'README', '.hermes/workflows/')) or suffix in DOC_SUFFIXES:
        events.add('v.governance.changed.docs')
    if suffix in CODE_SUFFIXES or p.split('/')[0] in {
        'platform-backend', 'ecommerce-backend', 'menu-backend', 'kyc-backend',
        'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend', 'tools'
    } or name in {'package.json', 'go.mod', 'pyproject.toml', 'Makefile'}:
        events.add('v.governance.changed.code')
    if (suffix in FRONTEND_SUFFIXES and any(part in p for part in FRONTEND_PATH_PARTS)) or p.split('/')[0] in {
        'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend'
    }:
        events.add('v.governance.changed.frontend')
    return events


def git_files(repo: Path, mode: str) -> list[str]:
    commands = {
        'staged': ['git', 'diff', '--name-only', '--cached'],
        'working': ['git', 'diff', '--name-only'],
        'head': ['git', 'diff', '--name-only', 'HEAD'],
        'pre-push': ['git', 'diff', '--name-only', '@{u}...HEAD'],
    }
    try:
        proc = subprocess.run(commands[mode], cwd=repo, text=True, capture_output=True, timeout=30)
        if proc.returncode != 0 and mode == 'pre-push':
            proc = subprocess.run(['git', 'diff', '--name-only', 'HEAD~1...HEAD'], cwd=repo, text=True, capture_output=True, timeout=30)
        if proc.returncode != 0:
            return []
        try:
            prefix = str(repo.resolve().relative_to(V_ROOT.resolve()))
        except Exception:
            prefix = repo.name
        return [norm(str(Path(prefix) / line.strip())) for line in proc.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def frontend_implementation_files(files: list[str], repo: Path | None = None) -> list[str]:
    frontend_roots = {'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend'}
    repo_name = repo.name if repo else ''
    result = []
    for file in files:
        p = norm(file)
        suffix = Path(p).suffix.lower()
        parts = p.split('/')
        if suffix not in FRONTEND_SUFFIXES or not parts:
            continue
        if parts[0] in frontend_roots:
            result.append(p)
            continue
        if repo_name in frontend_roots:
            result.append(norm(str(Path(repo_name) / p)))
    return result


def auto_bootstrap_frontend_workflow(files: list[str], source: str, timeout: int) -> dict:
    if not files:
        return {'status': 'SKIPPED', 'reason': 'no frontend implementation files'}
    first = norm(files[0])
    project = first.split('/')[0]
    stem = re.sub(r'[^a-zA-Z0-9]+', '-', first).strip('-').lower() or 'frontend-implementation'
    task_id = f'auto-{stem}'[:96].rstrip('-')
    task = {
        'id': task_id,
        'title': f'Auto-governed frontend implementation: {first}',
        'description': 'Production frontend implementation file change; default to C-risk prototype-first workflow bootstrap when no explicit workflow is supplied.',
        'project': project,
        'project_root': project,
        'changed_files': files,
        'source': source,
    }
    outdir = SELF_ROOT / 'reports' / 'v-continuous-governance-trigger'
    outdir.mkdir(parents=True, exist_ok=True)
    task_path = outdir / 'auto-frontend-task.json'
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding='utf-8')
    argv = [
        sys.executable, 'scripts/frontend_risk_router.py',
        '--root', str(SELF_ROOT),
        '--task-json', str(task_path),
        '--expect-risk', 'C',
        '--init-workflow',
        '--format', 'json',
    ]
    try:
        proc = subprocess.run(argv, cwd=SELF_ROOT, text=True, capture_output=True, timeout=timeout + 30)
        payload = None
        try:
            payload = json.loads(proc.stdout) if proc.stdout.strip() else None
        except Exception:
            payload = None
        workflow = None
        if isinstance(payload, dict):
            for item in payload.get('results', []):
                if isinstance(item, dict) and item.get('initialized_workflow'):
                    workflow = item.get('initialized_workflow')
                    break
        return {
            'status': 'PASS' if proc.returncode == 0 and workflow else 'FAIL',
            'exit_code': proc.returncode,
            'workflow': workflow,
            'task_json': str(task_path),
            'stdout': proc.stdout[-4000:],
            'stderr': proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired:
        return {'status': 'FAIL', 'exit_code': 124, 'workflow': None, 'task_json': str(task_path), 'stdout': '', 'stderr': 'frontend auto-bootstrap timeout'}
    except Exception as exc:
        return {'status': 'FAIL', 'exit_code': 127, 'workflow': None, 'task_json': str(task_path), 'stdout': '', 'stderr': f'frontend auto-bootstrap failed: {exc}'}


def workflow_path_has_symlink(path: Path, stop: Path) -> bool:
    try:
        stop = stop.resolve()
    except Exception:
        return True
    cur = path
    chain = [cur]
    while cur != stop and cur != cur.parent:
        cur = cur.parent
        chain.append(cur)
    return any(p.is_symlink() for p in chain)


def validate_governed_workflow(raw: str | None) -> tuple[str | None, dict | None]:
    if not raw:
        return None, None
    governed = (SELF_ROOT / '.hermes/workflows').resolve()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = SELF_ROOT / candidate
    try:
        resolved = candidate.resolve()
        resolved.relative_to(governed)
    except Exception:
        return None, {'status': 'BLOCKED', 'exit_code': 1, 'stdout': '', 'stderr': 'frontend workflow must stay under governed .hermes/workflows'}
    if workflow_path_has_symlink(candidate, governed) or resolved.is_symlink():
        return None, {'status': 'BLOCKED', 'exit_code': 1, 'stdout': '', 'stderr': 'frontend workflow path must not contain symlinks'}
    critical = ['FRONTEND_WORKFLOW_STATE.json', 'FRONTEND_EVIDENCE_MANIFEST.json', 'PROJECT_ADAPTER.yaml']
    for name in critical:
        p = resolved / name
        if p.is_symlink():
            return None, {'status': 'BLOCKED', 'exit_code': 1, 'stdout': '', 'stderr': f'frontend workflow critical file is symlink: {name}'}
    return str(resolved), None


def run_before_implementation_gate(workflow: str | None, timeout: int) -> dict:
    if not workflow:
        return {'status': 'BLOCKED', 'exit_code': 1, 'stdout': '', 'stderr': 'frontend workflow is required for implementation enforcement'}
    argv = [
        sys.executable, 'scripts/frontend_before_implementation_gate.py',
        '--root', str(SELF_ROOT), '--workflow', workflow, '--format', 'json',
    ]
    try:
        proc = subprocess.run(argv, cwd=SELF_ROOT, text=True, capture_output=True, timeout=timeout + 30)
        return {'status': 'PASS' if proc.returncode == 0 else 'BLOCKED', 'exit_code': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-4000:]}
    except subprocess.TimeoutExpired:
        return {'status': 'BLOCKED', 'exit_code': 124, 'stdout': '', 'stderr': 'frontend before-implementation gate timeout'}
    except Exception as exc:
        return {'status': 'BLOCKED', 'exit_code': 127, 'stdout': '', 'stderr': f'frontend before-implementation gate failed: {exc}'}


def run_business_gate_selector(files: list[str], dry_run: bool, run_gates: bool, timeout: int) -> dict:
    if not files:
        return {'status': 'NOOP', 'selected_gates': [], 'executions': [], 'findings': []}
    argv = [
        sys.executable, 'scripts/v_business_gate_selector.py',
        '--root', str(SELF_ROOT),
        '--format', 'json',
        '--timeout', str(timeout),
    ]
    if dry_run:
        argv.append('--dry-run')
    if run_gates:
        argv.append('--run')
    for file in files:
        argv.extend(['--changed-file', file])
    try:
        proc = subprocess.run(argv, cwd=SELF_ROOT, text=True, capture_output=True, timeout=timeout + 30)
        payload = None
        try:
            payload = json.loads(proc.stdout) if proc.stdout.strip() else None
        except Exception:
            payload = None
        if isinstance(payload, dict):
            payload.setdefault('exit_code', proc.returncode)
            payload.setdefault('stdout', proc.stdout[-4000:])
            payload.setdefault('stderr', proc.stderr[-4000:])
            return payload
        return {'status': 'FAIL' if proc.returncode else 'PASS', 'exit_code': proc.returncode, 'selected_gates': [], 'executions': [], 'findings': [], 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-4000:]}
    except subprocess.TimeoutExpired:
        return {'status': 'FAIL', 'exit_code': 124, 'selected_gates': [], 'executions': [], 'findings': [], 'stdout': '', 'stderr': 'business gate selector timeout'}
    except Exception as exc:
        return {'status': 'FAIL', 'exit_code': 127, 'selected_gates': [], 'executions': [], 'findings': [], 'stdout': '', 'stderr': f'business gate selector failed: {exc}'}


def trigger(event: str, files: list[str], source: str, dry_run: bool, timeout: int, business_gates: dict | None = None) -> dict:
    payload = {
        'source': source,
        'changed_files': files,
        'target_root': str(V_ROOT),
        'triggered_by': 'v_continuous_governance_trigger.py',
    }
    if business_gates is not None:
        payload['business_gates'] = business_gates
    argv = [
        sys.executable, '-m', 'selfcheck', 'trigger', '--root', str(SELF_ROOT),
        '--event', event, '--source', source, '--payload', json.dumps(payload, ensure_ascii=False),
        '--timeout', str(timeout),
    ]
    if dry_run:
        argv.append('--dry-run')
    try:
        proc = subprocess.run(argv, cwd=SELF_ROOT, text=True, capture_output=True, timeout=timeout + 30)
        return {'event': event, 'exit_code': proc.returncode, 'stdout': proc.stdout[-4000:], 'stderr': proc.stderr[-4000:]}
    except subprocess.TimeoutExpired:
        return {'event': event, 'exit_code': 124, 'stdout': '', 'stderr': 'selfcheck trigger timeout'}
    except Exception as exc:
        return {'event': event, 'exit_code': 127, 'stdout': '', 'stderr': f'selfcheck trigger failed: {exc}'}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo-root', default='.')
    ap.add_argument('--changed-file', action='append', default=[])
    ap.add_argument('--git-mode', choices=['staged', 'working', 'head', 'pre-push'])
    ap.add_argument('--source', default='local')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--enforce-frontend-implementation', dest='enforce_frontend_implementation', action='store_true', default=True)
    ap.add_argument('--no-enforce-frontend-implementation', dest='enforce_frontend_implementation', action='store_false')
    ap.add_argument('--frontend-workflow')
    ap.add_argument('--auto-bootstrap-frontend-workflow', dest='auto_bootstrap_frontend_workflow', action='store_true', default=True)
    ap.add_argument('--no-auto-bootstrap-frontend-workflow', dest='auto_bootstrap_frontend_workflow', action='store_false')
    ap.add_argument('--run-business-gates', action='store_true', help='Run selected business-specific SelfCheck gates after changed-file selection. Default only reports selected gates.')
    ap.add_argument('--no-business-gate-selector', dest='business_gate_selector', action='store_false', default=True)
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    raw_files = list(args.changed_file)
    unsafe_files = [f for f in raw_files if unsafe_changed_path(f)]
    files = list(raw_files)
    if args.git_mode:
        git_discovered = git_files(repo, args.git_mode)
        unsafe_files += [f for f in git_discovered if unsafe_changed_path(f)]
        files += git_discovered
    files = sorted({norm(f) for f in files if f.strip() and not unsafe_changed_path(f)})
    events = sorted({event for file in files for event in events_for_path(file)})
    report = {
        'status': 'NOOP' if not events else 'PASS',
        'source': args.source,
        'repo_root': str(repo),
        'dry_run': args.dry_run,
        'changed_files': files,
        'unsafe_changed_files': unsafe_files,
        'events': [],
        'business_gate_selector': None,
        'frontend_auto_bootstrap': None,
        'frontend_implementation_gate': None,
    }
    failures = 0
    if unsafe_files:
        failures += 1
        report['frontend_implementation_gate'] = {'status': 'BLOCKED', 'exit_code': 1, 'stdout': '', 'stderr': 'unsafe changed-file path input', 'changed_files': unsafe_files}
    impl_files = frontend_implementation_files(files, repo)
    frontend_workflow = args.frontend_workflow
    if args.enforce_frontend_implementation and impl_files and args.auto_bootstrap_frontend_workflow and not frontend_workflow and not unsafe_files:
        bootstrap = auto_bootstrap_frontend_workflow(impl_files, args.source, args.timeout)
        report['frontend_auto_bootstrap'] = bootstrap
        frontend_workflow = bootstrap.get('workflow')
        if bootstrap.get('status') != 'PASS':
            failures += 1
    if args.enforce_frontend_implementation and impl_files:
        frontend_workflow, workflow_error = validate_governed_workflow(frontend_workflow)
        if workflow_error:
            gate = workflow_error
        else:
            gate = run_before_implementation_gate(frontend_workflow, args.timeout)
        gate['changed_files'] = impl_files
        report['frontend_implementation_gate'] = gate
        if gate.get('exit_code') != 0:
            failures += 1
    business_gate_report = None
    if args.business_gate_selector and not unsafe_files:
        business_gate_report = run_business_gate_selector(files, args.dry_run, args.run_business_gates, args.timeout)
        report['business_gate_selector'] = business_gate_report
        if business_gate_report.get('exit_code', 0) != 0:
            failures += 1
    for event in events:
        result = trigger(event, files, args.source, args.dry_run, args.timeout, business_gate_report)
        report['events'].append(result)
        if result['exit_code'] != 0:
            failures += 1
    if failures:
        report['status'] = 'FAIL'
    out = SELF_ROOT / 'reports' / 'v-continuous-governance-trigger'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'latest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
