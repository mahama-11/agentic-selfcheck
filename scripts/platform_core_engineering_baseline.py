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

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    yaml = None

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
RUNTIME_JOB_STATUS_ASSIGN_RE = re.compile(r'\b(?:job|locked|runtimeJob|runtime_job)\.(?:Status|Stage)\b\s*=(?!=)')
IDEMPOTENCY_RE = re.compile(r'(?i)(idempotency[-_ ]?key|IdempotencyKey|idempotency_key)')
RAW_DB_RE = re.compile(r'\b(db|tx|conn)\.(Exec|Raw|Table|Where|Create|Save|Updates?|Delete)\s*\(')
ROUTE_RE = re.compile(r'\.(GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Group)\s*\(\s*["\']([^"\']+)')
ROUTE_CALL_RE = re.compile(r'(?P<receiver>[A-Za-z_][A-Za-z0-9_\.]*)\s*\.\s*(?P<method>GET|POST|PUT|PATCH|DELETE|OPTIONS|HEAD|Group)\s*\(\s*["\'](?P<path>[^"\']+)')
GROUP_ASSIGN_RE = re.compile(r'(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*(?::=|=)\s*(?P<receiver>[A-Za-z_][A-Za-z0-9_\.]*)\s*\.\s*Group\s*\(\s*["\'](?P<path>[^"\']+)')
NAMED_HANDLER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?$')
SEMANTIC_CONTRACT_RE = re.compile(
    r'(?i)(@Param|@Success|@Failure|request\b|response\b|responses\b|response\.SuccessResponse|envelope|body\b|query\b|path\s+param|returns?\b|data\b|schema\b)'
)
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
DEFAULT_PRODUCT_CLASSIFICATION_CONFIG = Path(__file__).resolve().parents[1] / 'config/platform-product-literal-classification.yaml'
DEFAULT_ROUTE_SEMANTIC_ALLOWLIST_CONFIG = Path(__file__).resolve().parents[1] / 'config/platform-route-semantic-allowlist.yaml'
ALLOWED_PRODUCT_LITERAL_CLASSIFICATIONS = {
    'generic_config_data',
    'adapter_projection',
    'devseed_demo_fixture',
    'docs_tests_migrations',
}


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


def load_product_literal_classifications(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding='utf-8')
        if yaml is not None:
            payload = yaml.safe_load(text) or {}
        else:
            payload = json.loads(text)
    except Exception:
        return []
    entries = payload.get('classifications', []) if isinstance(payload, dict) else []
    return [entry for entry in entries if isinstance(entry, dict)]


def load_route_semantic_allowlist(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        text = path.read_text(encoding='utf-8')
        if yaml is not None:
            payload = yaml.safe_load(text) or {}
        else:
            payload = json.loads(text)
    except Exception:
        return set()
    routes = payload.get('routes', []) if isinstance(payload, dict) else []
    allowed: set[str] = set()
    for item in routes:
        if not isinstance(item, dict):
            continue
        method = str(item.get('method', '')).upper().strip()
        route_path = route_signature_token(str(item.get('path', '')).strip())
        if method and route_path:
            allowed.add(f'{method} {route_path}')
    return allowed


def line_in_ranges(line: int, ranges: Any) -> bool:
    if not ranges:
        return True
    if not isinstance(ranges, list):
        return False
    for item in ranges:
        if not isinstance(item, dict):
            continue
        start = int(item.get('start', 0) or 0)
        end = int(item.get('end', start) or start)
        if start <= line <= end:
            return True
    return False


def classify_product_literal(rel: str, line: int, classifications: list[dict[str, Any]]) -> dict[str, Any] | None:
    for entry in classifications:
        patterns = entry.get('path_patterns', [])
        if isinstance(patterns, str):
            patterns = [patterns]
        if not any(fnmatch.fnmatch(rel, str(pattern)) for pattern in patterns):
            continue
        if not line_in_ranges(line, entry.get('line_ranges')):
            continue
        return entry
    return None


def window(lines: list[str], idx: int, radius: int = 4) -> str:
    lo = max(0, idx - radius)
    hi = min(len(lines), idx + radius + 1)
    return '\n'.join(lines[lo:hi])


def enclosing_go_func(lines: list[str], idx: int) -> str:
    for line in reversed(lines[:idx]):
        match = re.search(r'\bfunc\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(', line)
        if match:
            return match.group(1)
    return ''


def split_go_call_args(arg_text: str) -> list[str]:
    args: list[str] = []
    current: list[str] = []
    depth = 0
    quote = ''
    escaped = False
    for ch in arg_text:
        current.append(ch)
        if quote:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == quote:
                quote = ''
            continue
        if ch in {'"', "'", '`'}:
            quote = ch
        elif ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth = max(0, depth - 1)
        elif ch == ',' and depth == 0:
            args.append(''.join(current[:-1]).strip())
            current = []
    tail = ''.join(current).strip()
    if tail:
        args.append(tail)
    return args


def route_call_args(line: str, start: int) -> list[str]:
    call_start = line.find('(', start)
    if call_start < 0:
        return []
    depth = 0
    quote = ''
    escaped = False
    for pos in range(call_start, len(line)):
        ch = line[pos]
        if quote:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == quote:
                quote = ''
            continue
        if ch in {'"', "'", '`'}:
            quote = ch
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return split_go_call_args(line[call_start + 1:pos])
    return []


def extract_named_handler(args: list[str]) -> tuple[str, str]:
    if len(args) < 2:
        return '', 'missing'
    handler_args = [arg.strip() for arg in args[1:] if arg.strip()]
    if not handler_args:
        return '', 'missing'
    final = handler_args[-1]
    if final.startswith('func') or 'func(' in final:
        return '', 'inline'
    if NAMED_HANDLER_RE.match(final):
        return final, 'named'
    return '', 'ambiguous'


def is_approved_runtime_job_status_write(rel: str, func_name: str) -> bool:
    if rel.endswith('_test.go'):
        return True
    approved = {'ApplyRuntimeJobTransition', 'applyRuntimeJobTransitionFields', 'CreateRuntimeJob'}
    return rel.endswith('platform-backend/internal/modules/runtime/runtime_job_state_machine.go') and func_name in approved


def scan_file(path: Path, root: Path, findings: list[dict[str, Any]], stats: dict[str, int], profile: str = 'core', product_classifications: list[dict[str, Any]] | None = None) -> None:
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

        if profile == 'runtime' and rel.startswith('platform-backend/internal/modules/runtime/') and path.suffix == '.go' and RUNTIME_JOB_STATUS_ASSIGN_RE.search(line):
            func_name = enclosing_go_func(lines, idx)
            if is_approved_runtime_job_status_write(rel, func_name):
                add(findings, 'runtime_job_state_machine_ratchet', 'info', rel, idx, f'approved RuntimeJob Status/Stage write boundary: {func_name}', stripped)
            else:
                add(findings, 'runtime_job_state_machine_ratchet', 'error', rel, idx, 'RuntimeJob Status/Stage writes must use the canonical runtime job transition API; only the state-machine helper and creation initialization are approved', stripped)
            stats['runtime_job_state_machine_ratchet'] += 1

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
            classification = classify_product_literal(rel, idx, product_classifications or [])
            classification_name = str((classification or {}).get('classification', 'unclassified'))
            classification_id = str((classification or {}).get('id', 'unclassified'))
            justification = str((classification or {}).get('justification', 'no committed product literal classification matched this path/line'))
            severity = 'info' if classification_name in ALLOWED_PRODUCT_LITERAL_CLASSIFICATIONS else 'error'
            if classification_name == 'violation':
                severity = 'error'
            add(
                findings,
                'product_hardcode_classifier',
                severity,
                rel,
                idx,
                f'product literal classification={classification_name} id={classification_id}; {justification}',
                stripped,
            )
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


def join_route_paths(prefix: str, path_part: str) -> str:
    if not prefix:
        return route_signature_token(path_part)
    return route_signature_token('/'.join([prefix.rstrip('/'), path_part.lstrip('/')]))


def extract_route_signatures(path: Path, root: Path) -> list[dict[str, Any]]:
    rel = norm(path.relative_to(root))
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    signatures: list[dict[str, Any]] = []
    group_prefixes: dict[str, str] = {}
    for idx, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('//'):
            continue
        # Track common Gin nested-group composition:
        #   v1 := router.Group("/api/v1")
        #   auth := v1.Group("/auth")
        #   auth.POST("/register", handler)
        # Literal simple receivers get composed; unknown receivers conservatively
        # fall back to the route literal instead of claiming a false full path.
        for group_match in GROUP_ASSIGN_RE.finditer(line):
            receiver = group_match.group('receiver').strip()
            path_part = group_match.group('path').strip()
            parent_prefix = group_prefixes.get(receiver, '')
            group_prefixes[group_match.group('var').strip()] = join_route_paths(parent_prefix, path_part)

        for match in ROUTE_CALL_RE.finditer(line):
            method = match.group('method').upper()
            path_part = match.group('path').strip()
            if method == 'GROUP':
                continue
            receiver = match.group('receiver').strip()
            prefix = group_prefixes.get(receiver, '')
            full_path = join_route_paths(prefix, path_part)
            args = route_call_args(line, match.start())
            handler, handler_kind = extract_named_handler(args)
            signatures.append({
                'method': method,
                'path': full_path,
                'file': rel,
                'line': idx,
                'evidence': stripped[:240],
                'handler': handler,
                'handler_kind': handler_kind,
            })
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


def route_contract_reference(signature: dict[str, Any], spec_text: str) -> dict[str, Any]:
    result = {'method_path': False, 'handler': False, 'semantic': False, 'window': ''}
    if not spec_text:
        return result
    route_path = str(signature['path'])
    method = str(signature['method']).lower()
    handler = str(signature.get('handler') or '')
    handler_tokens = {handler, handler.split('.')[-1] if handler else ''} - {''}
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
            local = '\n'.join(lines[max(0, idx - 8): min(len(lines), idx + 9)])
            # OpenAPI/YAML/JSON style: a path key with a nearby HTTP method key.
            # This deliberately does not accept path-only evidence, because a route
            # changed to POST must fail closed when only GET /path is documented.
            method_key = re.search(rf'(?im)^\s*["\']?{re.escape(method)}["\']?\s*:', local)
            if markdown_route or method_key:
                result['method_path'] = True
                result['window'] = local[:1200]
                result['semantic'] = bool(SEMANTIC_CONTRACT_RE.search(local))
                result['handler'] = not handler_tokens or any(token in local for token in handler_tokens)
                return result
    return result


def route_has_contract_reference(signature: dict[str, Any], spec_text: str) -> bool:
    ref = route_contract_reference(signature, spec_text)
    return bool(ref['method_path'] and ref['semantic'] and (str(signature.get('handler_kind')) != 'named' or ref['handler']))


def route_openapi_check(root: Path, changed_files: list[str], findings: list[dict[str, Any]], stats: dict[str, int], route_allowlist: set[str] | None = None) -> None:
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

    # Always evaluate discovered live route signatures for Platform profiles. This
    # avoids a clean-checkout blind spot where CI/verifier invocations do not pass
    # changed files and `git status` is empty, while route/OpenAPI drift still needs
    # conservative evidence. Changed route files are still used for fail-closed
    # diagnostics when a changed file contains no parseable route signature.
    signatures_to_check = changed_signatures if route_changed_files and changed_signatures else all_signatures
    if signatures_to_check and spec_files:
        for sig in signatures_to_check:
            ref = route_contract_reference(sig, spec_text)
            route_key = f"{sig['method']} {sig['path']}"
            allowlisted_legacy_gap = route_key in (route_allowlist or set())
            if not ref['method_path']:
                add(
                    findings,
                    'route_openapi_drift_check',
                    'info' if allowlisted_legacy_gap else 'error',
                    str(sig['file']),
                    int(sig['line']),
                    f"route signature {sig['method']} {sig['path']} has no matching INTERNAL_API_CONTRACT/OpenAPI reference" + ('; allowed as committed legacy route coverage debt' if allowlisted_legacy_gap else ''),
                    str(sig['evidence']),
                )
                continue
            if str(sig.get('handler_kind')) == 'named' and not ref['handler']:
                add(
                    findings,
                    'route_openapi_drift_check',
                    'info' if allowlisted_legacy_gap else 'error',
                    str(sig['file']),
                    int(sig['line']),
                    f"route signature {sig['method']} {sig['path']} names handler {sig.get('handler')} but nearby contract/OpenAPI evidence does not name that handler",
                    str(sig['evidence']),
                )
            elif str(sig.get('handler_kind')) in {'inline', 'ambiguous', 'missing'}:
                add(
                    findings,
                    'route_openapi_drift_check',
                    'warning',
                    str(sig['file']),
                    int(sig['line']),
                    f"route signature {sig['method']} {sig['path']} has {sig.get('handler_kind')} handler evidence; semantic route diff cannot require handler mapping automatically",
                    str(sig['evidence']),
                )
            if not ref['semantic']:
                add(
                    findings,
                    'route_openapi_drift_check',
                    'info' if allowlisted_legacy_gap else 'error',
                    str(sig['file']),
                    int(sig['line']),
                    f"route signature {sig['method']} {sig['path']} has only method/path evidence; require nearby request/response/envelope evidence" + ('; allowed as committed legacy route coverage debt' if allowlisted_legacy_gap else ''),
                    str(sig['evidence']),
                )
    elif route_changed_files and not changed_signatures and not spec_changed:
        add(findings, 'route_openapi_drift_check', 'error', '<changed-files>', 0, 'route/handler changed but no route signature or contract/spec change was detected; fail closed for manual contract review', ', '.join(route_changed_files[:20]))
    elif not spec_files:
        add(findings, 'route_openapi_drift_check', 'warning', 'platform-backend', 0, 'no OpenAPI/spec file discovered; route contract drift check recorded route count only', '')
    stats['route_openapi_checked_signatures'] = len(signatures_to_check) if spec_files else 0
    stats['route_openapi_spec_files'] = len(set(spec_files))


def summarize(findings: list[dict[str, Any]]) -> str:
    severities = {str(f.get('severity')) for f in findings}
    if {'critical', 'error'} & severities:
        return 'NEEDS_REPAIR'
    if 'needs_human' in severities:
        return 'NEEDS_HUMAN'
    if any(f.get('severity') == 'warning' and f.get('scanner') == 'route_openapi_drift_check' for f in findings):
        return 'PASS_WITH_NOTES'
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
    ap.add_argument('--product-classification-config', default=str(DEFAULT_PRODUCT_CLASSIFICATION_CONFIG), help='Machine-readable product literal classification inventory.')
    ap.add_argument('--route-semantic-allowlist-config', default=str(DEFAULT_ROUTE_SEMANTIC_ALLOWLIST_CONFIG), help='Machine-readable inventory of committed legacy route semantic coverage gaps.')
    ap.add_argument('--format', choices=['json', 'text'], default='json')
    args = ap.parse_args()

    root = Path(args.target_root).resolve()
    findings: list[dict[str, Any]] = []
    stats = {
        'raw_status_write_scanner': 0,
        'runtime_job_state_machine_ratchet': 0,
        'unscoped_idempotency_scanner': 0,
        'product_hardcode_classifier': 0,
        'service_raw_db_expansion_scanner': 0,
        'route_openapi_drift_check': 0,
    }
    changed_files: list[str] = []
    files: list[Path] = []
    product_classification_path = Path(args.product_classification_config).resolve()
    product_classifications = load_product_literal_classifications(product_classification_path)
    route_allowlist_path = Path(args.route_semantic_allowlist_config).resolve()
    route_allowlist = load_route_semantic_allowlist(route_allowlist_path)
    if not root.exists():
        add(findings, 'target_root', 'error', str(root), 0, 'target root does not exist', '')
    else:
        changed_files = [norm(f) for f in args.changed_file] or discover_changed_files(root)
        files = iter_files(root, args.include, args.profile)
        if not files:
            add(findings, 'target_files', 'error', str(root), 0, 'no platform core files were available to scan', '')
        for path in files:
            scan_file(path, root, findings, stats, args.profile, product_classifications)
        route_openapi_check(root, changed_files, findings, stats, route_allowlist)

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
        'product_classification_config': str(product_classification_path),
        'product_classification_entries': len(product_classifications),
        'route_semantic_allowlist_config': str(route_allowlist_path),
        'route_semantic_allowlist_entries': len(route_allowlist),
        'fail_closed': 'NEEDS_REPAIR, NEEDS_HUMAN, critical, and error findings return non-zero.',
        'scanners': [
            'raw_status_write_scanner',
            'runtime_job_state_machine_ratchet',
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
