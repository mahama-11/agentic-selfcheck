#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SELF_ROOT = Path('/root/work/agentic-selfcheck')
V_ROOT = Path('/root/work/v')
V_WORKTREES_ROOT = Path('/root/work/v-worktrees')
STATE_PATH = SELF_ROOT / 'reports' / 'v-working-tree-governance-watchdog' / 'state.json'
LATEST_PATH = SELF_ROOT / 'reports' / 'v-working-tree-governance-watchdog' / 'latest.json'
MAX_CHANGED_SOURCE_LINES = 800
MAX_CHANGED_SOURCE_BYTES = 1024 * 1024
SOURCE_SUFFIXES = {'.py', '.go', '.ts', '.tsx', '.js', '.jsx', '.vue', '.svelte'}
CANONICAL_REPOS = [
    'platform-backend', 'ecommerce-backend', 'menu-backend', 'kyc-backend',
    'platform-frontend', 'ecommerce-frontend', 'menu-frontend', 'kyc-frontend',
]


def _timeout_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, bytes):
        return value.decode(errors='replace')
    return str(value)


def run(cmd: list[str], cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stderr = _timeout_text(exc.stderr)
        message = f"command timed out after {timeout}s: {' '.join(cmd)}"
        if stderr:
            stderr = stderr + '\n' + message
        else:
            stderr = message
        return subprocess.CompletedProcess(cmd, 124, _timeout_text(exc.stdout), stderr)


def discover_repos() -> list[Path]:
    repos: list[Path] = []
    seen: set[Path] = set()
    for name in CANONICAL_REPOS:
        repo = V_ROOT / name
        if (repo / '.git').exists() and repo not in seen:
            repos.append(repo)
            seen.add(repo)
    for git_path in V_ROOT.glob('*/.git'):
        repo = git_path.parent
        if repo not in seen:
            repos.append(repo)
            seen.add(repo)
    if V_WORKTREES_ROOT.exists():
        for git_path in sorted([*V_WORKTREES_ROOT.glob('*/.git'), *V_WORKTREES_ROOT.glob('*/*/.git')]):
            repo = git_path.parent
            if repo not in seen:
                repos.append(repo)
                seen.add(repo)
    return repos


def canonical_prefix(repo: Path) -> str:
    name = repo.name
    for canonical in sorted(CANONICAL_REPOS, key=len, reverse=True):
        if name == canonical or name.startswith(canonical + '-'):
            return canonical
    return name


def porcelain_changed_files(repo: Path) -> tuple[list[str], dict[str, Any] | None]:
    cp = run(['git', 'status', '--porcelain=v1', '-z'], repo, timeout=30)
    if cp.returncode != 0:
        return [], {
            'severity': 'error',
            'failure_type': 'GIT_STATUS_TIMEOUT' if cp.returncode == 124 else 'GIT_STATUS_FAILED',
            'repo': str(repo),
            'returncode': cp.returncode,
            'stderr': cp.stderr[-2000:],
            'message': 'unable to inspect repository working tree with git status; watchdog cannot safely classify it as clean',
            'recommended_action': 'inspect repository health/locks/filesystem load, then rerun the working-tree governance watchdog',
        }
    files: list[str] = []
    entries = cp.stdout.split('\0')
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        if status.startswith('R') or status.startswith('C'):
            # porcelain -z emits old path in this entry and new path in next entry.
            if i < len(entries) and entries[i]:
                path = entries[i]
                i += 1
        if path:
            normalized = path.replace('\\\\', '/')
            candidate = repo / normalized
            if candidate.is_dir():
                for child in candidate.rglob('*'):
                    if child.is_file():
                        files.append(child.relative_to(repo).as_posix())
            else:
                files.append(normalized)
    return sorted(set(files)), None


def file_digest(repo: Path, rel: str) -> str:
    path = repo / rel
    if not path.exists() or path.is_dir():
        return 'missing-or-dir'
    h = hashlib.sha256()
    try:
        with path.open('rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception as exc:
        return f'error:{type(exc).__name__}'


def repo_signature(repo: Path, files: list[str]) -> str:
    h = hashlib.sha256()
    h.update('\n'.join(files).encode())
    # Include tracked diff bytes so repeated edits to the same files retrigger.
    cp = run(['git', 'diff', '--no-ext-diff', '--binary', 'HEAD', '--', *files], repo, timeout=120) if files else None
    if cp and cp.stdout:
        h.update(cp.stdout.encode(errors='ignore'))
    for rel in files:
        # Untracked files are not in git diff HEAD; hash all file contents as a cheap universal guard.
        h.update(rel.encode())
        h.update(file_digest(repo, rel).encode())
    return h.hexdigest()


def prefixed_files(repo: Path, files: list[str]) -> list[str]:
    prefix = canonical_prefix(repo)
    return [f'{prefix}/{f}' for f in files]


def large_changed_file_findings(repo: Path, files: list[str]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for rel in files:
        path = repo / rel
        if not path.exists() or path.is_dir() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        lines = None
        if size <= MAX_CHANGED_SOURCE_BYTES * 8:
            try:
                lines = path.read_text(encoding='utf-8', errors='ignore').count('\n') + 1
            except Exception:
                lines = None
        reasons = []
        if size > MAX_CHANGED_SOURCE_BYTES:
            reasons.append(f'{size} bytes > {MAX_CHANGED_SOURCE_BYTES}')
        if lines is not None and lines > MAX_CHANGED_SOURCE_LINES:
            reasons.append(f'{lines} lines > {MAX_CHANGED_SOURCE_LINES}')
        if reasons:
            findings.append({
                'severity': 'error',
                'failure_type': 'LARGE_CHANGED_SOURCE_FILE',
                'path': f'{canonical_prefix(repo)}/{rel}',
                'bytes': size,
                'lines': lines,
                'thresholds': {'max_source_lines': MAX_CHANGED_SOURCE_LINES, 'max_source_bytes': MAX_CHANGED_SOURCE_BYTES},
                'message': 'changed source file exceeds locality threshold: ' + '; '.join(reasons),
                'recommended_action': 'split/refactor in an isolated worktree with tests, or attach explicit human approval before merge',
            })
    return findings


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {'repos': {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {'repos': {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def select_business_gates(files: list[str]) -> dict[str, Any]:
    argv = [sys.executable, 'scripts/v_business_gate_selector.py', '--root', str(SELF_ROOT), '--format', 'json']
    for file in files:
        argv.extend(['--changed-file', file])
    cp = run(argv, SELF_ROOT, timeout=60)
    try:
        payload = json.loads(cp.stdout) if cp.stdout.strip() else {}
    except Exception:
        payload = {}
    payload['exit_code'] = cp.returncode
    payload['stderr'] = cp.stderr[-2000:]
    return payload


def run_trigger(repo: Path, files: list[str], timeout: int) -> dict[str, Any]:
    argv = [
        sys.executable, 'scripts/v_continuous_governance_trigger.py',
        '--repo-root', str(repo),
        '--source', 'cron',
        '--timeout', str(timeout),
        '--run-business-gates',
        '--no-enforce-frontend-implementation',
    ]
    for file in files:
        argv.extend(['--changed-file', file])
    cp = run(argv, SELF_ROOT, timeout=timeout + 90)
    try:
        parsed = json.loads(cp.stdout) if cp.stdout.strip() else {}
        payload: dict[str, Any] = parsed if isinstance(parsed, dict) else {'raw_stdout': cp.stdout[-4000:]}
    except Exception:
        payload: dict[str, Any] = {'raw_stdout': cp.stdout[-4000:]}
    payload['exit_code'] = cp.returncode
    payload['stderr'] = cp.stderr[-4000:]
    return payload


def run_failure_closed_loop() -> dict[str, Any]:
    argv = [
        sys.executable, 'scripts/v_failure_closed_loop.py', 'ingest',
        '--root', str(SELF_ROOT),
        '--report', str(LATEST_PATH),
        '--source', 'working-tree-watchdog',
        '--format', 'json',
    ]
    cp = run(argv, SELF_ROOT, timeout=60)
    try:
        payload = json.loads(cp.stdout) if cp.stdout.strip() else {}
    except Exception:
        payload: dict[str, Any] = {'raw_stdout': cp.stdout[-4000:]}
    payload['exit_code'] = cp.returncode
    payload['stderr'] = cp.stderr[-3000:]
    return payload


GATE_LABELS = {
    'platform-core-engineering-baseline': 'Platform 核心工程基线',
    'platform-ops-visible-baseline': 'Platform 运维可见性基线',
    'platform-runtime-state-machine-baseline': '运行时状态机基线',
    'platform-runtime-business-integration-safety': '运行时业务集成安全',
    'platform-financial-business-consistency': 'Platform 财务业务一致性',
    'platform-financial-consistency-baseline': 'Platform 财务一致性基线',
    'ecommerce-critical-journey-release-gate': 'Ecom 核心链路发布门禁',
    'ecommerce-large-source-locality-guard': 'Ecom 大文件/局部性门禁',
    'ecommerce-v1-listing-export-gate': 'Ecom V1 Listing/导出门禁',
    'ecommerce-v2-prep-sandbox-lowlevel': 'Ecom V2 Prep/Sandbox 底层门禁',
}


FAILURE_LABELS = {
    'LARGE_CHANGED_SOURCE_FILE': '改动文件过大，超过局部性阈值',
    'BUSINESS_GATE_SELECTOR_FAILED': '业务门禁选择器失败',
    'GIT_STATUS_TIMEOUT': 'Git 状态检查超时',
    'GIT_STATUS_FAILED': 'Git 状态检查失败',
}


def cn_gate(gate: str) -> str:
    return GATE_LABELS.get(gate, gate)


def summarize_failure(failure: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    repo = failure.get('repo', '未知仓库')
    lines.append(f"- 仓库：`{repo}`")
    lines.append(f"  - 改动数：{failure.get('changed_count', 0)}")
    gates = [cn_gate(str(g)) for g in (failure.get('selected_gates') or [])]
    if gates:
        lines.append('  - 触发门禁：' + '、'.join(gates))
    failure_type = failure.get('failure_type')
    if failure_type:
        lines.append('  - 失败原因：' + FAILURE_LABELS.get(str(failure_type), str(failure_type)))
    findings = failure.get('findings') or []
    for finding in findings[:3]:
        path = finding.get('path')
        detail = []
        if finding.get('lines') is not None:
            detail.append(f"{finding.get('lines')} 行")
        if finding.get('bytes') is not None:
            detail.append(f"{finding.get('bytes')} 字节")
        thresholds = finding.get('thresholds') or {}
        threshold = thresholds.get('max_source_lines')
        if path:
            suffix = f"（{', '.join(detail)}" + (f"，阈值 {threshold} 行" if threshold else '') + '）'
            lines.append(f"  - 文件：`{path}`{suffix}")
    trigger = failure.get('trigger') or {}
    frontend_gate = trigger.get('frontend_implementation_gate') or {}
    unsafe = frontend_gate.get('changed_files') or trigger.get('unsafe_changed_files') or []
    if unsafe:
        lines.append('  - 前端实现门禁阻断：changed-file 里包含目录路径，需改成具体文件：' + '、'.join(f'`{p}`' for p in unsafe[:5]))
    stderr = (frontend_gate.get('stderr') or trigger.get('stderr') or '').strip()
    if stderr:
        lines.append(f"  - 原始错误：`{stderr[-300:]}`")
    return lines


def print_text_report(report: dict[str, Any]) -> None:
    if report['status'] != 'FAIL':
        return
    failures = report.get('failures') or []
    print('⚠️ V 工作区业务门禁未通过')
    print('')
    print(f"结论：发现 {len(failures)} 个需要工程处理的问题；这是门禁报告，不是要求郭凯手工修。")
    print('')
    print('失败项：')
    for failure in failures:
        for line in summarize_failure(failure):
            print(line)
    closed_loop = report.get('failure_closed_loop') or {}
    if closed_loop:
        status = closed_loop.get('status') or '未知'
        ledger = closed_loop.get('ledger')
        generated = closed_loop.get('generated_at')
        print('')
        print('闭环处理：')
        print(f"- 已写入失败闭环账本，状态：`{status}`")
        if generated:
            print(f"- 更新时间：{generated}")
        if ledger:
            print(f"- 账本：`{ledger}`")
    print('')
    print('建议动作：')
    print('- 工程代理继续拆分过大的文件改动；如出现目录级 changed-file，门禁会自动展开为具体文件后重跑。')
    print('- 只有涉及产品取舍、删除/回滚/合并批准时，才需要郭凯决策。')
    print(f"- 详细 JSON：`{LATEST_PATH}`")


def main() -> int:
    ap = argparse.ArgumentParser(description='Run continuous V working-tree governance before commit/push.')
    ap.add_argument('--quiet-seconds', type=int, default=900, help='Require dirty signature to be stable this long before running heavy gates.')
    ap.add_argument('--timeout', type=int, default=300)
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--format', choices=['json', 'text'], default='text')
    args = ap.parse_args()

    now = time.time()
    state = load_state()
    state.setdefault('repos', {})
    report: dict[str, Any] = {
        'status': 'SILENT',
        'source': 'v_working_tree_governance_watchdog.py',
        'quiet_seconds': args.quiet_seconds,
        'checked_at_epoch': now,
        'repos': [],
        'executed': [],
        'failures': [],
    }

    for repo in discover_repos():
        rel_files, status_failure = porcelain_changed_files(repo)
        key = str(repo)
        entry = state['repos'].setdefault(key, {})
        if status_failure:
            entry['last_status'] = status_failure.get('failure_type')
            failure = {
                'repo': key,
                'status': 'FAIL',
                'changed_count': 0,
                'selected_gates': [],
                'failure_type': status_failure.get('failure_type'),
                'git_status': status_failure,
            }
            report['repos'].append(failure)
            report['failures'].append(failure)
            continue
        if not rel_files:
            entry.clear()
            report['repos'].append({'repo': key, 'status': 'CLEAN'})
            continue
        full_files = prefixed_files(repo, rel_files)
        selector = select_business_gates(full_files)
        selected = selector.get('selected_gates') or []
        sig = repo_signature(repo, rel_files)
        if entry.get('signature') != sig:
            entry.update({'signature': sig, 'first_seen_at': now, 'last_change_at': now, 'last_seen_files': full_files, 'last_status': 'PENDING_QUIET'})
        age = now - float(entry.get('last_change_at') or now)
        repo_report = {
            'repo': key,
            'status': 'DIRTY',
            'changed_count': len(full_files),
            'selected_gates': [g.get('feature') for g in selected if isinstance(g, dict)],
            'signature_age_seconds': round(age, 1),
        }
        selector_failed = selector.get('exit_code') != 0 or selector.get('status') == 'FAIL' or bool(selector.get('findings'))
        if selector_failed:
            entry['last_status'] = 'FAIL'
            failure = {**repo_report, 'status': 'FAIL', 'failure_type': 'BUSINESS_GATE_SELECTOR_FAILED', 'selector': selector}
            report['repos'].append(failure)
            report['failures'].append(failure)
            continue
        large_findings = large_changed_file_findings(repo, rel_files)
        if large_findings:
            entry['last_status'] = 'FAIL'
            failure = {**repo_report, 'status': 'FAIL', 'failure_type': 'LARGE_CHANGED_SOURCE_FILE', 'findings': large_findings}
            report['repos'].append(failure)
            report['failures'].append(failure)
            continue
        if not selected:
            entry['last_status'] = 'NO_BUSINESS_GATES'
            report['repos'].append({**repo_report, 'status': 'NO_BUSINESS_GATES', 'selector': selector})
            continue
        already_passed = entry.get('last_run_signature') == sig and entry.get('last_status') == 'PASS'
        if already_passed and not args.force:
            report['repos'].append({**repo_report, 'status': 'ALREADY_PASSED'})
            continue
        if age < args.quiet_seconds and not args.force:
            report['repos'].append({**repo_report, 'status': 'WAITING_FOR_QUIET_WINDOW'})
            continue
        trigger = run_trigger(repo, full_files, args.timeout)
        ok = trigger.get('exit_code') == 0 and trigger.get('status') == 'PASS'
        entry['last_run_at'] = now
        entry['last_run_signature'] = sig
        entry['last_status'] = 'PASS' if ok else 'FAIL'
        entry['last_report'] = trigger
        executed = {**repo_report, 'status': 'PASS' if ok else 'FAIL', 'trigger': trigger}
        report['executed'].append(executed)
        report['repos'].append(executed)
        if not ok:
            report['failures'].append(executed)

    if report['failures']:
        report['status'] = 'FAIL'
    elif report['executed']:
        # For no_agent cron this is intentionally silent on PASS to avoid notification noise.
        report['status'] = 'PASS_SILENT'
    save_state(state)
    LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if report['failures']:
        report['failure_closed_loop'] = run_failure_closed_loop()
        LATEST_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    if args.format == 'json':
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)
        # PASS/SILENT prints nothing so cron no_agent stays quiet.
    # Business-gate failures are reported in stdout with Chinese formatting.
    # Keep the process exit code 0 so the scheduler does not wrap it in an English
    # "Cron job failed / Script exited" system error. Infrastructure failures are
    # still fail-closed inside the report itself.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
