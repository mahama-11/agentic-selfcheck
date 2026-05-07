#!/usr/bin/env python3
"""SelfCheck gate for Platform template media source readiness.

This gate intentionally does not import media or write Platform DB rows. It reads the
prepared real asset manifest and proves whether each referenced source file exists
under configured source roots.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path(
    "/root/work/v/platform-backend/testdata/templateops/real-import/template_ops_real_asset_manifest.json"
)
DEFAULT_REPORT = Path(
    "/root/work/agentic-selfcheck/reports/platform-template-media-association/platform-template-media-association-gate.json"
)
WORKSPACE_ROOT = Path("/root/work/v")
PLATFORM_BACKEND_ROOT = WORKSPACE_ROOT / "platform-backend"
SELFCHECK_ROOT = Path("/root/work/agentic-selfcheck")


def parse_bool_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def split_env_roots(value: str) -> list[str]:
    return [part for part in value.split(":") if part]


def normalize_roots(cli_roots: list[str], env_value: str) -> list[Path]:
    """Return deterministic source roots with CLI first, env second, defaults last."""
    raw_roots: list[str] = []
    raw_roots.extend(cli_roots)
    raw_roots.extend(split_env_roots(env_value))
    raw_roots.extend(
        [
            str(WORKSPACE_ROOT),
            str(PLATFORM_BACKEND_ROOT),
            str(SELFCHECK_ROOT),
            str(Path.cwd()),
        ]
    )

    roots: list[Path] = []
    seen: set[str] = set()
    for raw in raw_roots:
        root = Path(raw).expanduser()
        if not root.is_absolute():
            root = (Path.cwd() / root)
        key = str(root.resolve(strict=False))
        if key not in seen:
            seen.add(key)
            roots.append(Path(key))
    return roots


def safe_asset_ref(asset_ref: Any) -> str | None:
    if not isinstance(asset_ref, str) or not asset_ref.strip():
        return None
    asset_ref = asset_ref.strip().replace("\\", "/")
    path = Path(asset_ref)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        return None
    return asset_ref


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, dict):
        raise ValueError("asset manifest must be a JSON object")
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("asset manifest must contain an items array")
    return data


def item_identity(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return {
        "sourceRef": item.get("sourceRef"),
        "assetRef": item.get("assetRef"),
        "storageFileName": item.get("storageFileName"),
        "templateRef": metadata.get("templateID") or metadata.get("templateCode") or metadata.get("externalCode"),
    }


def resolve_items(items: list[Any], roots: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolved: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for index, raw_item in enumerate(items):
        item = raw_item if isinstance(raw_item, dict) else {}
        ident = item_identity(item)
        asset_ref = safe_asset_ref(item.get("assetRef"))
        candidate_paths = [str(root / asset_ref) for root in roots] if asset_ref else []

        if not asset_ref:
            missing.append(
                {
                    "index": index,
                    **ident,
                    "candidatePaths": candidate_paths,
                    "reason": "invalid_asset_ref",
                }
            )
            continue

        resolved_path: Path | None = None
        matched_root: Path | None = None
        for root in roots:
            candidate = root / asset_ref
            if candidate.is_file():
                resolved_path = candidate
                matched_root = root
                break

        if resolved_path is None:
            missing.append(
                {
                    "index": index,
                    **ident,
                    "assetRef": asset_ref,
                    "candidatePaths": candidate_paths,
                    "reason": "source_file_not_found",
                }
            )
        else:
            resolved.append(
                {
                    "index": index,
                    **ident,
                    "assetRef": asset_ref,
                    "resolvedPath": str(resolved_path),
                    "matchedRoot": str(matched_root) if matched_root is not None else None,
                    "candidatePaths": candidate_paths,
                }
            )

    return resolved, missing


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.asset_manifest).expanduser().resolve(strict=False)
    report_path = Path(args.report).expanduser().resolve(strict=False)
    roots = normalize_roots(args.asset_source_root, os.environ.get("TEMPLATE_ASSET_SOURCE_ROOTS", ""))
    manifest = load_manifest(manifest_path)
    items = manifest.get("items", [])
    resolved, missing = resolve_items(items, roots)
    status = "MEDIA_READY" if not missing else "MEDIA_SOURCE_MISSING"

    report: dict[str, Any] = {
        "status": status,
        "project": args.project,
        "feature": args.feature,
        "assetManifestPath": str(manifest_path),
        "reportPath": str(report_path),
        "assetManifestVersion": manifest.get("version"),
        "assetManifestGeneratedBy": manifest.get("generatedBy"),
        "assetManifestGeneratedAt": manifest.get("generatedAt"),
        "assetManifestItemCount": len(items),
        "resolvedAssetCount": len(resolved),
        "missingAssetCount": len(missing),
        "manifestMissingAssetCount": len(manifest.get("missingAssets", [])) if isinstance(manifest.get("missingAssets"), list) else None,
        "sourceRootsChecked": [str(root) for root in roots],
        "requireReady": bool(args.require_ready),
        "importAttempted": False,
        "importBlockedReason": None if status == "MEDIA_READY" else "source_files_missing",
        "resolvedAssetSample": resolved[:10],
        "resolvedAssets": resolved,
        "missingAssetSample": missing[:10],
        "missingAssets": missing,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Platform template media source readiness.")
    parser.add_argument("--project", default="v-workspace")
    parser.add_argument("--feature", default="platform-template-media-association")
    parser.add_argument("--asset-manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--asset-source-root", action="append", default=[], help="Repeatable root to resolve assetRef paths under.")
    parser.add_argument("--require-ready", action="store_true", default=parse_bool_env("TEMPLATE_MEDIA_REQUIRE_READY"), help="Exit nonzero unless every assetRef resolves.")
    args = parser.parse_args()

    try:
        report = build_report(args)
    except Exception as exc:
        failure = {
            "status": "FAIL",
            "project": args.project,
            "feature": args.feature,
            "assetManifestPath": str(Path(args.asset_manifest).expanduser()),
            "failure": f"{type(exc).__name__}: {exc}",
        }
        write_report(Path(args.report).expanduser().resolve(strict=False), failure)
        print(json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True))
        return 1

    write_report(Path(args.report).expanduser().resolve(strict=False), report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))

    if args.require_ready and report["status"] != "MEDIA_READY":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
