#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {'.go', '.ts', '.tsx', '.js', '.jsx', '.py', '.sql', '.yaml', '.yml', '.json', '.md'}
CORE_PREFIXES = (
    'platform-backend/internal/modules/runtime/',
    'platform-backend/internal/modules/wallet/',
    'platform-backend/internal/modules/metering/',
    'platform-backend/internal/modules/billing/',
    'platform-backend/internal/modules/storage/',
    'platform-backend/internal/modules/auth/',
    'platform-backend/internal/modules/identity/',
    'platform-backend/internal/modules/access/',
    'platform-backend/internal/modules/catalog/',
    'platform-backend/internal/modules/commercial/',
    'platform-backend/internal/modules/templateops/',
    'platform-backend/internal/router',
    'platform-backend/internal/routes',
    'platform-backend/docs/',
    'platform-frontend/src/',
)
PROFILE_FEATURE = {
    'core': 'platform-core-engineering-baseline',
    'runtime': 'platform-runtime-state-machine-baseline',
    'financial': 'platform-financial-consistency-baseline',
}
PROFILE_PREFIXES = {
    'core': CORE_PREFIXES,
    'runtime': (
        'platform-backend/internal/modules/runtime/',
        'platform-backend/internal/router',
        'platform-backend/internal/routes',
        'platform-backend/docs/',
    ),
    'financial': (
        'platform-backend/internal/modules/wallet/',
        'platform-backend/internal/modules/metering/',
        'platform-backend/internal/modules/billing/',
        'platform-backend/internal/modules/catalog/',
        'platform-backend/internal/modules/commercial/',
        'platform-backend/internal/modules/quota/',
        'platform-backend/internal/modules/incentive/',
        'platform-backend/internal/router',
        'platform-backend/internal/routes',
        'platform-backend/docs/',
    ),
}
PRODUCT_LITERAL_RE = re.compile(r'(?i)(product[_-]?code|productCode|ProductCode)\s*[:=]\s*["\'](ecommerce|kyc|menu)["\']|["\'](ecommerce|kyc|menu)["\']')
STATUS_WRITE_RE = re.compile(r'(?i)(\.Update(?:Column|Columns|s)?\s*\(\s*["\']status["\']|\bSET\s+status\s*=)')
STATUS_ASSIGN_RE = re.compile(r'(?i)(\b\w+\.(?:Status|Stage)\b\s*=(?!=)|\bupdates\s*\[\s*["\']status["\']\s*\]\s*=(?!=))')
IDEMPOTENCY_RE = re.compile(r'(?i)(idempotency[-_ ]?key|IdempotencyKey|idempotency_key)')
RAW_DB_RE = re.compile(r'\b(db|tx|conn)\.(Exec|Raw|Table|Where|Create|Save|Updates?|Delete)\s*\(')
ROUTE_RE = re.compile(r'\.(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Group)\s*\(\s*["\']([^"\']+)')
ROUTE_FILE_RE = re.compile(r'(?i)(platform-backend/internal/(?:router|routes)/|/handler|handler\.go|router|routes)')
SPEC_PATTERNS = [
    'platform-backend/docs/openapi*',
    'platform-backend/docs/openapi/**',
    'platform-backend/docs/**/*openapi*',
    'platform-backend/docs/INTERNAL_API_CONTRACT.md',
    'platform-backend/api/**/*.yaml',
    'platform-backend/api/**/*.yml',
    'platform-backend/api/**/*.json',
]


def norm(path: Path | str) -> str:
    return str(path).replace('\\', '/').removeprefix('./')


def iter_files(root: Path, includes: list[str], profile: str = 'core') -> list[Path]:
    files: list[Path] = []
    if includes:
        for raw in includes:
            p = root / raw
            if p.is_file() and is_text(p):
                files.append(p)
        return sorted(set(files))
    for prefix in PROFILE_PREFIXES.get(profile, CORE_PREFIXES):
        base = root / prefix
        if base.is_file() and is_text(base):
            files.append(base)
        elif base.is_dir():
            for p in base.rglob('*'):
                if p.is_file() and is_text(p):
                    files.append(p)
    return sorted(set(files))


def is_text(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES and not any(part in {'node_modules', '.git', 'dist', 'build', 'vendor'} for part in path.parts)


def add(findings: list[dict[str, Any]], scanner: str, severity: str, file: str, line: int, message: str, evidence: str) -> None:
    findings.append({'scanner': scanner, 'severity': severity, 'file': file, 'line': line, 'message': message, 'evidence': evidence[:240]})


def window(lines: list[str], idx: int, radius: int = 4) -> str:
    lo = max(0, idx - radius)
    hi = min(len(lines), idx + radius + 1)
    return '\n'.join(lines[lo:hi])


def scan_file(path: Path, root: Path, findings: list[dict[str, Any]], stats: dict[str, int]) -> None:
    rel = norm(path.relative_to(root))
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError as exc:
        add(findings, 'readability', 'error', rel, 0, f'cannot read platform core file: {exc}', '')
        return
    lines = text.splitlines()

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            continue
        if STATUS_WRITE_RE.search(line):
            ctx = window(lines, idx - 1)
            guarded = re.search(r'(?i)(state_machine|transition|allowed.*status|validate.*status|status.*transition|runtime.*state|domain.*event)', ctx)
            severity = 'warning' if guarded else 'error'
            add(findings, 'raw_status_write_scanner', severity, rel, idx, 'raw status write must go through an explicit domain transition/state-machine boundary', stripped)
            stats['raw_status_write_scanner'] += 1

        if STATUS_ASSIGN_RE.search(line):
            ctx = window(lines, idx - 1, radius=8)
            guarded = re.search(r'(?i)(state_machine|transition|allowed.*status|validate.*status|status.*transition|runtime.*state|domain.*event)', ctx)
            severity = 'info' if path.suffix in {'.md', '.tsx', '.ts', '.jsx', '.js'} else 'warning'
            if guarded:
                severity = 'info'
            add(findings, 'raw_status_write_scanner', severity, rel, idx, 'direct status/stage assignment must be guarded by an explicit domain transition/state-machine boundary', stripped)
            stats['raw_status_write_scanner'] += 1

        if IDEMPOTENCY_RE.search(line):
            ctx = window(lines, idx - 1, radius=8)
            function_ctx = window(lines, idx - 1, radius=40)
            has_boundary_validator = ('validateRuntimeJobIdempotencyBoundary' in text or 'runtimeJobMatchesIdempotencyBoundary' in text or 'FindRuntimeJobByIdempotencyKey(input.ProductCode' in text) and re.search(
                r'(?i)(validateRuntimeJobIdempotencyBoundary|runtimeJobMatchesIdempotencyBoundary|FindRuntimeJobByIdempotencyKey|product|organization|source|task)', function_ctx
            )
            scoped = re.search(r'(?i)(org|organization|tenant|workspace|account|user|subject|product|sku|source|task)', ctx) or has_boundary_validator
            if path.suffix in {'.md', '.yaml', '.yml', '.json'}:
                add(findings, 'unscoped_idempotency_scanner', 'info', rel, idx, 'idempotency contract reference classified in non-code file', stripped)
            elif stripped.startswith('var Err') or stripped.startswith('const Err'):
                add(findings, 'unscoped_idempotency_scanner', 'info', rel, idx, 'idempotency error/constant declaration classified as non-usage', stripped)
            elif not scoped:
                add(findings, 'unscoped_idempotency_scanner', 'error', rel, idx, 'idempotency key usage is not visibly scoped by org/user/product/workspace in the local context', stripped)
            else:
                add(findings, 'unscoped_idempotency_scanner', 'info', rel, idx, 'idempotency key usage appears locally scoped', stripped)
            stats['unscoped_idempotency_scanner'] += 1

        if PRODUCT_LITERAL_RE.search(line):
            allowed = any(token in rel for token in ('/catalog/', '/commercial/', '/templateops/', '/docs/', 'seed', 'migration', 'test'))
            severity = 'info' if allowed else 'warning'
            add(findings, 'product_hardcode_classifier', severity, rel, idx, 'product literal classified; shared platform code should prefer catalog/config where practical', stripped)
            stats['product_hardcode_classifier'] += 1

        if RAW_DB_RE.search(line) and rel.endswith('service.go'):
            ctx = window(lines, idx - 1)
            expansion = re.search(r'(?i)(CREATE\s+TABLE|ALTER\s+TABLE|DROP\s+TABLE|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|SELECT\s+\*)', ctx)
            if expansion:
                add(findings, 'service_raw_db_expansion_scanner', 'error', rel, idx, 'service-layer raw DB expansion/query detected; move to repository/migration/contracted persistence boundary', stripped)
            else:
                add(findings, 'service_raw_db_expansion_scanner', 'warning', rel, idx, 'service-layer raw DB primitive detected; verify it is not expanding persistence contract', stripped)
            stats['service_raw_db_expansion_scanner'] += 1

        if ROUTE_RE.search(line):
            stats['route_openapi_drift_check'] += 1


def route_signature_token(path: str) -> str:
    token = re.sub(r':([A-Za-z0-9_]+)', r'{\1}', path.strip())
    token = re.sub(r'//+', '/', token)
    return token.rstrip('/') or '/'


def extract_route_signatures(path: Path, root: Path) -> list[dict[str, Any]]:
    rel = norm(path.relative_to(root))
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    signatures: list[dict[str, Any]] = []
    group_stack: list[str] = []
    for idx, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            continue
        for match in ROUTE_RE.finditer(line):
            method = match.group(1).upper()
            path_part = match.group(2).strip()
            if method == 'GROUP':
                group_stack.append(path_part.rstrip('/'))
                group_stack = group_stack[-3:]
                continue
            prefix = '' if path_part.startswith('/') or not group_stack else group_stack[-1]
            full_path = route_signature_token('/'.join([prefix.rstrip('/'), path_part.lstrip('/')]) if prefix else path_part)
            signatures.append({'method': method, 'path': full_path, 'file': rel, 'line': idx, 'evidence': stripped[:240]})
    return signatures


def discover_route_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for prefix in ('platform-backend/internal/router', 'platform-backend/internal/routes', 'platform-backend/internal/modules'):
        base = root / prefix
        if not base.exists():
            continue
        if base.is_file() and base.suffix == '.go':
            candidates.append(base)
            continue
        for p in base.rglob('*.go'):
            rel = norm(p.relative_to(root))
            if ROUTE_FILE_RE.search(rel):
                candidates.append(p)
    return sorted(set(candidates))


def load_spec_text(root: Path, spec_files: list[Path]) -> str:
    chunks: list[str] = []
    for path in sorted(set(spec_files)):
        if not path.is_file() or not is_text(path):
            continue
        try:
            chunks.append(path.read_text(encoding='utf-8', errors='replace'))
        except OSError:
            continue
    return '\n'.join(chunks)


def route_has_contract_reference(signature: dict[str, Any], spec_text: str) -> bool:
    if not spec_text:
        return False
    route_path = str(signature['path'])
    method = str(signature['method']).lower()
    candidates = {
        route_path,
        route_path.replace('{', ':').replace('}', ''),
        re.sub(r'\{[^/]+\}', '{}', route_path),
    }
    lines = spec_text.splitlines()
    for idx, line in enumerate(lines):
        for candidate in sorted((c for c in candidates if c), key=len, reverse=True):
            if candidate not in line:
                continue
            escaped = re.escape(candidate)
            markdown_route = re.search(rf'(?i)\b{re.escape(method)}\b\s+`?{escaped}(?:`|\b|/|\?|#|$)', line)
            if markdown_route:
                return True
            local = '\n'.join(lines[max(0, idx - 8): min(len(lines), idx + 9)])
            # OpenAPI/YAML/JSON style: a path key with a nearby HTTP method key.
            # This deliberately does not accept path-only evidence, because a route
            # changed to POST must fail closed when only GET /path is documented.
            method_key = re.search(rf'(?im)^\s*["\']?{re.escape(method)}["\']?\s*:', local)
            if method_key:
                return True
    return False


def route_openapi_check(root: Path, changed_files: list[str], findings: list[dict[str, Any]], stats: dict[str, int]) -> None:
    normalized_changes = [norm(f) for f in changed_files]
    route_changed_files = [f for f in normalized_changes if ROUTE_FILE_RE.search(f) and f.endswith(('.go', '.md', '.yaml', '.yml', '.json'))]
    spec_files = [p for pat in SPEC_PATTERNS for p in root.glob(pat)]
    spec_changed = any(fnmatch.fnmatch(f, pat) for f in normalized_changes for pat in SPEC_PATTERNS)
    all_signatures: list[dict[str, Any]] = []
    for route_file in discover_route_files(root):
        all_signatures.extend(extract_route_signatures(route_file, root))
    stats['route_openapi_signatures'] = len(all_signatures)

    changed_signatures: list[dict[str, Any]] = []
    for changed in route_changed_files:
        p = root / changed
        if p.is_file():
            changed_signatures.extend(extract_route_signatures(p, root))
    spec_text = load_spec_text(root, spec_files)

    if route_changed_files:
        if changed_signatures:
            for sig in changed_signatures:
                if not route_has_contract_reference(sig, spec_text):
                    add(
                        findings,
                        'route_openapi_drift_check',
                        'error',
                        str(sig['file']),
                        int(sig['line']),
                        f"route signature {sig['method']} {sig['path']} has no matching INTERNAL_API_CONTRACT/OpenAPI reference",
                        str(sig['evidence']),
                    )
        elif not spec_changed:
            add(findings, 'route_openapi_drift_check', 'error', '<changed-files>', 0, 'route/handler changed but no route signature or contract/spec change was detected; fail closed for manual contract review', ', '.join(route_changed_files[:20]))
    elif not spec_files:
        add(findings, 'route_openapi_drift_check', 'warning', 'platform-backend', 0, 'no OpenAPI/spec file discovered; route contract drift check recorded route count only', '')
    stats['route_openapi_spec_files'] = len(set(spec_files))


def summarize(findings: list[dict[str, Any]]) -> str:
    severities = {str(f.get('severity')) for f in findings}
    if {'critical', 'error'} & severities:
        return 'NEEDS_REPAIR'
    if 'needs_human' in severities:
        return 'NEEDS_HUMAN'
    return 'PASS'


def discover_changed_files(root: Path) -> list[str]:
    changed: list[str] = []
    for repo_name in ('platform-backend', 'platform-frontend'):
        repo = root / repo_name
        if not (repo / '.git').exists():
            continue
        try:
            out = subprocess.check_output(['git', '-C', str(repo), 'status', '--short'], text=True, stderr=subprocess.DEVNULL)
        except Exception:
            continue
        for raw in out.splitlines():
            if not raw.strip():
                continue
            rel = raw[3:].strip()
            if ' -> ' in rel:
                rel = rel.split(' -> ', 1)[1]
            changed.append(f'{repo_name}/{rel}')
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description='Platform Engineering Governance deterministic scanners.')
    ap.add_argument('--target-root', default=os.environ.get('V_WORKSPACE_ROOT', '/root/work/v'))
    ap.add_argument('--report', default='reports/platform-core-engineering-baseline/platform-core-engineering-baseline.json')
    ap.add_argument('--changed-file', action='append', default=[])
    ap.add_argument('--include', action='append', default=[], help='Limit scan to repo-relative file path; may be repeated.')
    ap.add_argument('--profile', choices=['core', 'runtime', 'financial'], default='core', help='Scanner profile/report feature identity.')
    ap.add_argument('--format', choices=['json', 'text'], default='json')
    args = ap.parse_args()

    root = Path(args.target_root).resolve()
    findings: list[dict[str, Any]] = []
    stats = {
        'raw_status_write_scanner': 0,
        'unscoped_idempotency_scanner': 0,
        'product_hardcode_classifier': 0,
        'service_raw_db_expansion_scanner': 0,
        'route_openapi_drift_check': 0,
    }
    changed_files: list[str] = []
    files: list[Path] = []
    if not root.exists():
        add(findings, 'target_root', 'error', str(root), 0, 'target root does not exist', '')
    else:
        changed_files = [norm(f) for f in args.changed_file] or discover_changed_files(root)
        files = iter_files(root, args.include, args.profile)
        if not files:
            add(findings, 'target_files', 'error', str(root), 0, 'no platform core files were available to scan', '')
        for path in files:
            scan_file(path, root, findings, stats)
        route_openapi_check(root, changed_files, findings, stats)

    status = summarize(findings)
    report = {
        'feature': PROFILE_FEATURE[args.profile],
        'profile': args.profile,
        'status': status,
        'target_root': str(root),
        'files_scanned': len(files),
        'stats': stats,
        'findings': findings,
        'changed_files': changed_files,
        'fail_closed': 'NEEDS_REPAIR, NEEDS_HUMAN, critical, and error findings return non-zero.',
        'scanners': [
            'raw_status_write_scanner',
            'unscoped_idempotency_scanner',
            'product_hardcode_classifier',
            'service_raw_db_expansion_scanner',
            'route_openapi_drift_check',
        ],
    }
    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = Path.cwd() / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    if args.format == 'json':
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"status={status} profile={args.profile} files_scanned={len(files)} findings={len(findings)} report={report_path}")
        for finding in findings[:50]:
            print(f"{finding['severity']} {finding['scanner']} {finding['file']}:{finding['line']} {finding['message']}")
    return 0 if status not in {'NEEDS_REPAIR', 'NEEDS_HUMAN'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
