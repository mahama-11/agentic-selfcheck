#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CSV_COLUMNS = [
    "product_code",
    "template_id",
    "slug",
    "name",
    "summary",
    "status",
    "scope",
    "managed_source",
    "cover_asset_url",
    "cover_asset_id",
    "recommend_score",
    "platforms_json",
    "tags_json",
    "series",
    "capability_type",
    "modality",
    "raw_json",
    "detail_json",
]


def run(cmd: list[str], cwd: Path, timeout: int = 120) -> dict[str, Any]:
    started = time.time()
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)
    return {
        "cmd": cmd,
        "cwd": str(cwd),
        "exit_code": proc.returncode,
        "duration_seconds": round(time.time() - started, 3),
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def fail(message: str, report: dict[str, Any], code: int = 1) -> None:
    report["status"] = "FAIL"
    report["failure"] = message
    write_report(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(code)


def write_report(report: dict[str, Any]) -> None:
    root = Path(report["selfcheck_root"])
    out = root / "reports" / "platform-template-mastering"
    out.mkdir(parents=True, exist_ok=True)
    (out / "platform-template-mastering-gate.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def live_preview_if_available(platform_url: str, token: str, csv_content: str) -> dict[str, Any]:
    if not platform_url:
        return {"status": "SKIPPED", "reason": "PLATFORM_BASE_URL not set"}
    try:
        urllib.request.urlopen(platform_url.rstrip("/") + "/healthz", timeout=2).read()
    except Exception as exc:
        return {"status": "SKIPPED", "reason": f"platform health unavailable: {type(exc).__name__}"}
    if not token:
        return {"status": "SKIPPED", "reason": "PLATFORM_ADMIN_TOKEN not set; static route/service tests cover preview path"}
    payload = json.dumps({"content": csv_content}).encode("utf-8")
    req = urllib.request.Request(
        platform_url.rstrip("/") + "/api/v1/template-ops/import/csv/preview",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return {"status": "PASS", "http_status": resp.status, "code": body.get("code"), "summary": body.get("data", {}).get("summary", {})}
    except urllib.error.HTTPError as exc:
        return {"status": "FAIL", "http_status": exc.code, "reason": "preview API returned non-2xx"}
    except Exception as exc:
        return {"status": "FAIL", "reason": f"preview API call failed: {type(exc).__name__}"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="v-workspace")
    parser.add_argument("--feature", default="platform-template-mastering")
    args = parser.parse_args()

    selfcheck_root = Path(__file__).resolve().parents[1]
    workspace_root = Path("/root/work/v")
    platform_root = workspace_root / "platform-backend"
    report: dict[str, Any] = {
        "project": args.project,
        "feature": args.feature,
        "selfcheck_root": str(selfcheck_root),
        "workspace_root": str(workspace_root),
        "checks": {},
    }

    export_result = run(["python3", "scripts/export_real_template_ops_import.py"], platform_root)
    report["checks"]["exporter"] = export_result
    if export_result["exit_code"] != 0:
        fail("exporter failed", report)

    artifact_dir = platform_root / "testdata" / "templateops" / "real-import"
    csv_path = artifact_dir / "template_ops_real_import.csv"
    manifest_path = artifact_dir / "template_ops_real_asset_manifest.json"
    summary_path = artifact_dir / "template_ops_real_import_summary.json"
    for path in [csv_path, manifest_path, summary_path]:
        if not path.exists():
            fail(f"missing artifact: {path}", report)

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with csv_path.open("r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.get("product_code", "")] = counts.get(row.get("product_code", ""), 0) + 1
        for key in ["platforms_json", "tags_json", "raw_json", "detail_json"]:
            json.loads(row[key])

    validation = {
        "csv_columns": fieldnames,
        "row_count": len(rows),
        "product_counts": counts,
        "summary": summary,
        "asset_manifest_items": len(manifest.get("items", [])),
        "missing_asset_count": len(manifest.get("missingAssets", [])),
    }
    report["checks"]["artifact_validation"] = validation
    if fieldnames != CSV_COLUMNS:
        fail("CSV columns do not match Template Ops import contract", report)
    if len(rows) != 187 or counts.get("ecommerce") != 173 or counts.get("menu") != 14:
        fail("CSV row/product counts do not match expected 187 total / 173 ecommerce / 14 menu", report)
    if summary.get("templateCount") != 187 or summary.get("ecommerceTemplateCount") != 173 or summary.get("menuTemplateCount") != 14:
        fail("summary counts do not match expected source inventory", report)
    if len(manifest.get("items", [])) != 173:
        fail("asset manifest item count should expose 173 ecommerce example assets", report)

    router_text = (platform_root / "internal" / "router" / "router.go").read_text(encoding="utf-8")
    handler_text = (platform_root / "internal" / "modules" / "templateops" / "handler.go").read_text(encoding="utf-8")
    service_test_text = (platform_root / "internal" / "modules" / "templateops" / "service_test.go").read_text(encoding="utf-8")
    route_gate = {
        "preview_route_registered": 'POST("/import/csv/preview"' in router_text,
        "import_route_registered": 'POST("/import/csv"' in router_text,
        "preview_handler_calls_service": "PreviewImportCSV(c.Request.Context()" in handler_text,
        "service_preview_test_present": "TestTemplateOpsService_PreviewImportCSV" in service_test_text,
    }
    report["checks"]["platform_preview_import_path"] = route_gate
    if not all(route_gate.values()):
        fail("Platform preview/import path is not fully wired through router/handler/service test", report)

    go_test = run(["go", "test", "./internal/modules/templateops", "-run", "TestTemplateOpsService_(PreviewImportCSV|LoadPreparedRealImportBundle)", "-count=1"], platform_root, timeout=180)
    report["checks"]["platform_service_preview_tests"] = go_test
    if go_test["exit_code"] != 0:
        fail("Template Ops preview/loading service tests failed", report)

    csv_content = csv_path.read_text(encoding="utf-8")
    report["checks"]["live_platform_preview"] = live_preview_if_available(
        os.environ.get("PLATFORM_BASE_URL", "http://127.0.0.1:8195"),
        os.environ.get("PLATFORM_ADMIN_TOKEN", ""),
        csv_content,
    )
    if report["checks"]["live_platform_preview"].get("status") == "FAIL":
        fail("live Platform preview API failed", report)

    report["status"] = "PASS"
    write_report(report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
