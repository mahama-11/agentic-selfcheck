#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_V_ROOT = Path('/root/work/v')
MAX_SOURCE_LINES = 800
MAX_SOURCE_BYTES = 1024 * 1024
SOURCE_SUFFIXES = {'.go', '.ts', '.tsx', '.js', '.jsx', '.vue', '.svelte', '.py'}
SCAN_ROOTS = ('ecommerce-backend', 'ecommerce-frontend')
SKIP_DIRS = {
    '.git', 'node_modules', 'dist', 'build', 'coverage', '.vite', '.next', '.turbo',
    'tmp', 'temp', 'vendor', '__pycache__', '.pytest_cache', '.cache',
}

# Existing legacy files are allowed only until the dedicated refactor plan splits them.
# They must not grow. Remove each entry as soon as the file is split below threshold.
LEGACY_ALLOWLIST: dict[str, dict[str, Any]] = {
    'ecommerce-backend/internal/modules/imageruntime/handler_test.go': {'max_lines': 808, 'owner': 'backend-agent', 'task': 'RT-ECOM-IMAGERUNTIME-HANDLER-TEST'},
    'ecommerce-backend/internal/modules/imageruntime/service.go': {'max_lines': 1352, 'owner': 'backend-agent', 'task': 'RT-8E0A9384D933'},
    'ecommerce-backend/internal/modules/productcore/handler_test.go': {'max_lines': 1244, 'owner': 'backend-agent', 'task': 'RT-ECOM-PRODUCTCORE-HANDLER-TEST'},
    'ecommerce-backend/internal/modules/productcore/service.go': {'max_lines': 2351, 'owner': 'backend-agent', 'task': 'RT-E1CDB81CDD87'},
    'ecommerce-backend/internal/modules/visualworkflow/service.go': {'max_lines': 5870, 'owner': 'backend-agent', 'task': 'RT-06EC9EDE4F65'},
    'ecommerce-backend/internal/modules/visualworkflow/service_test.go': {'max_lines': 3333, 'owner': 'backend-agent', 'task': 'RT-F2EDDF815F2D'},
    'ecommerce-backend/internal/modules/visualworkflow/types.go': {'max_lines': 814, 'owner': 'backend-agent', 'task': 'RT-ECOM-VISUALWORKFLOW-TYPES'},
    'ecommerce-backend/internal/platform/client.go': {'max_lines': 887, 'owner': 'backend-agent', 'task': 'RT-ECOM-PLATFORM-CLIENT'},
    'ecommerce-backend/internal/repository/template_center_repository.go': {'max_lines': 1123, 'owner': 'backend-agent', 'task': 'RT-ECOM-TEMPLATE-REPOSITORY'},
    'ecommerce-frontend/src/i18n/en.ts': {'max_lines': 1597, 'owner': 'frontend-agent', 'task': 'RT-AB1D002289DD'},
    'ecommerce-frontend/src/i18n/zh.ts': {'max_lines': 1663, 'owner': 'frontend-agent', 'task': 'RT-C69E70D21FF8'},
    'ecommerce-frontend/src/pages/AgentTemplateMarketPage.tsx': {'max_lines': 1165, 'owner': 'frontend-agent', 'task': 'RT-ECOM-TEMPLATE-MARKET-PAGE'},
    'ecommerce-frontend/src/pages/AssetCommercePage.tsx': {'max_lines': 981, 'owner': 'frontend-agent', 'task': 'RT-ECOM-ASSET-COMMERCE-PAGE'},
    'ecommerce-frontend/src/pages/DesignWorkbenchPage.tsx': {'max_lines': 854, 'owner': 'frontend-agent', 'task': 'RT-ECOM-DESIGN-WORKBENCH-PAGE'},
    'ecommerce-frontend/src/pages/GenericPage.tsx': {'max_lines': 1395, 'owner': 'frontend-agent', 'task': 'RT-ECOM-GENERIC-PAGE'},
    'ecommerce-frontend/src/pages/ToolPage.tsx': {'max_lines': 1117, 'owner': 'frontend-agent', 'task': 'RT-ECOM-TOOL-PAGE'},
    'ecommerce-frontend/src/pages/product/ProductDetailPage.tsx': {'max_lines': 977, 'owner': 'frontend-agent', 'task': 'RT-ECOM-PRODUCT-DETAIL-PAGE'},
    'ecommerce-frontend/src/pages/product/components/ProductDetailTabs.tsx': {'max_lines': 866, 'owner': 'frontend-agent', 'task': 'RT-ECOM-PRODUCT-DETAIL-TABS'},
    'ecommerce-frontend/src/pages/production/PrepHubPage.tsx': {'max_lines': 1374, 'owner': 'frontend-agent', 'task': 'RT-ECOM-PREP-HUB'},
    'ecommerce-frontend/src/pages/production/SandboxPage.tsx': {'max_lines': 1510, 'owner': 'frontend-agent', 'task': 'RT-1EF8A28A9044'},
    'ecommerce-frontend/src/pages/production/WorkshopPage.tsx': {'max_lines': 1135, 'owner': 'frontend-agent', 'task': 'RT-ECOM-WORKSHOP-PAGE'},
    'ecommerce-frontend/src/services/product.ts': {'max_lines': 837, 'owner': 'frontend-agent', 'task': 'RT-ECOM-PRODUCT-SERVICE'},
    'ecommerce-frontend/src/services/production.ts': {'max_lines': 2031, 'owner': 'frontend-agent', 'task': 'RT-6D0700F9F8ED'},
}


def norm(path: Path | str) -> str:
    return str(path).replace('\\', '/').removeprefix('./')


def iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for scan_root in SCAN_ROOTS:
        base = root / scan_root
        if not base.exists():
            continue
        for path in base.rglob('*'):
            if not path.is_file():
                continue
            rel_parts = path.relative_to(root).parts
            if any(part in SKIP_DIRS for part in rel_parts):
                continue
            if path.suffix.lower() in SOURCE_SUFFIXES:
                files.append(path)
    return sorted(files)


def load_allowlist(path: str | None) -> dict[str, dict[str, Any]]:
    if not path:
        return dict(LEGACY_ALLOWLIST)
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('allowlist JSON must be an object keyed by repo-relative path')
    normalized: dict[str, dict[str, Any]] = {}
    for key, value in data.items():
        if not isinstance(value, dict):
            raise ValueError(f'allowlist entry must be an object: {key}')
        normalized[norm(key)] = value
    return normalized


def line_count(path: Path) -> int:
    with path.open('r', encoding='utf-8', errors='ignore') as fh:
        return sum(1 for _ in fh)


def scan(root: Path, allowlist: dict[str, dict[str, Any]], strict: bool) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    legacy_remaining: list[dict[str, Any]] = []
    scanned = 0
    oversized = 0
    for path in iter_source_files(root):
        scanned += 1
        rel = norm(path.relative_to(root))
        size = path.stat().st_size
        lines = line_count(path)
        over_lines = lines > MAX_SOURCE_LINES
        over_bytes = size > MAX_SOURCE_BYTES
        if not over_lines and not over_bytes:
            continue
        oversized += 1
        allowed = allowlist.get(rel)
        base = {
            'path': rel,
            'lines': lines,
            'bytes': size,
            'thresholds': {'max_source_lines': MAX_SOURCE_LINES, 'max_source_bytes': MAX_SOURCE_BYTES},
        }
        if allowed and not strict:
            max_lines = int(allowed.get('max_lines', MAX_SOURCE_LINES))
            max_bytes = int(allowed.get('max_bytes', MAX_SOURCE_BYTES * 32))
            if lines <= max_lines and size <= max_bytes:
                legacy_remaining.append({**base, 'task': allowed.get('task'), 'owner': allowed.get('owner'), 'status': 'LEGACY_REFACTOR_REQUIRED'})
                continue
            findings.append({
                **base,
                'severity': 'error',
                'failure_type': 'ECOMMERCE_LEGACY_LARGE_SOURCE_GREW',
                'message': f'legacy oversized Ecommerce source grew beyond baseline ({lines}>{max_lines} lines or {size}>{max_bytes} bytes); split before merge',
                'task': allowed.get('task'),
                'owner': allowed.get('owner'),
            })
            continue
        findings.append({
            **base,
            'severity': 'error',
            'failure_type': 'ECOMMERCE_LARGE_SOURCE_FILE',
            'message': 'Ecommerce source file exceeds locality threshold; split into cohesive files before merge',
        })
    status = 'FAIL' if findings else ('PASS_WITH_NOTES' if legacy_remaining else 'PASS')
    if strict and legacy_remaining:
        status = 'FAIL'
    return {
        'status': status,
        'strict': strict,
        'root': str(root),
        'scanned_source_files': scanned,
        'oversized_source_files': oversized,
        'findings': findings,
        'legacy_remaining': legacy_remaining,
        'allowlist_entries': sorted(allowlist),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Fail-closed guard for oversized Agent Ecommerce source files.')
    ap.add_argument('--v-root', default=str(DEFAULT_V_ROOT))
    ap.add_argument('--allowlist-json', help='Test-only override for legacy allowlist')
    ap.add_argument('--strict', action='store_true', help='Fail on every oversized file, including legacy allowlisted files')
    ap.add_argument('--format', choices=['json', 'text'], default='json')
    args = ap.parse_args()
    payload = scan(Path(args.v_root).resolve(), load_allowlist(args.allowlist_json), args.strict)
    if args.format == 'json':
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"status={payload['status']} scanned={payload['scanned_source_files']} oversized={payload['oversized_source_files']} legacy={len(payload['legacy_remaining'])} findings={len(payload['findings'])}")
        for finding in payload['findings']:
            print(f"ERROR {finding['path']}: {finding['message']}")
        for legacy in payload['legacy_remaining']:
            print(f"LEGACY {legacy['path']}: {legacy['lines']} lines task={legacy.get('task')}")
    return 0 if payload['status'] in {'PASS', 'PASS_WITH_NOTES'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
