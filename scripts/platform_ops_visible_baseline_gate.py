#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 15.0) -> dict[str, Any]:
    max_attempts = 4
    for attempt in range(max_attempts):
        resp = _fetch_json_once(url, method=method, payload=payload, headers=headers, timeout=timeout)
        if resp.get("status") != 429 or attempt == max_attempts - 1:
            if attempt:
                resp["retry_attempts"] = attempt
            time.sleep(0.08)
            return resp
        retry_after = 0.35 * (attempt + 1)
        parsed = resp.get("json")
        if isinstance(parsed, dict):
            retry_after_raw = parsed.get("retry_after") or parsed.get("retryAfter")
            try:
                retry_after = max(retry_after, float(retry_after_raw))
            except (TypeError, ValueError):
                pass
        time.sleep(retry_after)
    return resp


def _fetch_json_once(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 15.0) -> dict[str, Any]:
    started = time.time()
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {"User-Agent": "agentic-selfcheck/platform-ops-visible-baseline/0.1"}
    if body is not None:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(4 * 1024 * 1024).decode("utf-8", errors="replace")
            parsed: Any
            try:
                parsed = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = {"body_prefix": raw[:240], "parse_error": "json_decode"}
            return {"url": redact_url(url), "status": resp.status, "ok": 200 <= resp.status < 400, "duration_ms": round((time.time() - started) * 1000), "json": parsed}
    except urllib.error.HTTPError as e:
        raw = e.read(4096).decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"body_prefix": raw[:240]}
        return {"url": redact_url(url), "status": e.code, "ok": False, "duration_ms": round((time.time() - started) * 1000), "json": parsed}
    except Exception as e:
        return {"url": redact_url(url), "status": None, "ok": False, "duration_ms": round((time.time() - started) * 1000), "error": str(e)}


def redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    qs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe = [(k, "<redacted>" if "token" in k.lower() or "password" in k.lower() else v) for k, v in qs]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(safe), parsed.fragment))


def envelope_data(resp: dict[str, Any]) -> Any:
    parsed = resp.get("json")
    if isinstance(parsed, dict) and "data" in parsed:
        return parsed.get("data")
    return parsed


def extract_token(login: dict[str, Any]) -> str | None:
    data = envelope_data(login)
    if isinstance(data, dict):
        token = data.get("token") or data.get("access_token")
        return token if isinstance(token, str) and token else None
    return None


def items_from(resp: dict[str, Any]) -> list[dict[str, Any]]:
    data = envelope_data(resp)
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        raw = data.get("items") or data.get("list") or data.get("data")
        if isinstance(raw, list):
            return [x for x in raw if isinstance(x, dict)]
    return []


def total_from(resp: dict[str, Any]) -> int:
    data = envelope_data(resp)
    if isinstance(data, dict) and isinstance(data.get("total"), int):
        return int(data["total"])
    return len(items_from(resp))


def sync_total_from(resp: dict[str, Any]) -> int:
    data = envelope_data(resp)
    if isinstance(data, dict):
        total = data.get("total")
        if isinstance(total, int):
            return total
        items = data.get("items")
        if isinstance(items, list):
            return len(items)
    return 0


def count_items(resp: dict[str, Any]) -> int:
    return len(items_from(resp))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="v-workspace")
    ap.add_argument("--feature", default="platform-ops-visible-baseline")
    ap.add_argument("--platform-base", default=os.environ.get("PLATFORM_BASE_URL", "http://127.0.0.1:8195"))
    ap.add_argument("--email", default=os.environ.get("PLATFORM_DEV_ADMIN_EMAIL", "admin@verilocale.com"))
    ap.add_argument("--password-env", default="PLATFORM_DEV_ADMIN_PASSWORD")
    ap.add_argument("--report", default="reports/platform-ops-visible-baseline/platform-ops-visible-baseline-gate.json")
    ap.add_argument("--skip-sync", action="store_true")
    args = ap.parse_args()

    password = os.environ.get(args.password_env, "123qwe")
    login = fetch_json(args.platform_base + "/api/v1/auth/login", method="POST", payload={"email": args.email, "password": password})
    token = extract_token(login)
    auth = {"Authorization": "Bearer " + token} if token else {}

    sync = {"ok": True, "skipped": True}
    if token and not args.skip_sync:
        sync_url = args.platform_base + "/api/v1/template-ops/sync?" + urllib.parse.urlencode({"product_code": "ecommerce", "locale": "zh"})
        sync = fetch_json(sync_url, method="POST", headers=auth, timeout=60.0)

    tpl_url = args.platform_base + "/api/v1/template-ops/catalog?" + urllib.parse.urlencode({"product_code": "ecommerce", "limit": "200", "published_only": "true"})
    templates = fetch_json(tpl_url, headers=auth)
    template_items = items_from(templates)
    template_sample = template_items[:5]
    template_fields_ok = bool(template_items) and all(
        item.get("product_code") == "ecommerce" and item.get("template_ref") and item.get("template_id") and item.get("name")
        for item in template_sample
    )
    template_semantic_fields = any(item.get("modality") or item.get("series") or item.get("capability_type") or item.get("cover_asset_url") for item in template_sample)

    products = fetch_json(args.platform_base + "/api/v1/catalog/products", headers=auth)
    product_items = items_from(products)
    ecommerce_product = next((p for p in product_items if p.get("code") == "ecommerce"), {})
    product_id = ecommerce_product.get("id") or ecommerce_product.get("ID")

    def catalog(path: str) -> dict[str, Any]:
        if not product_id:
            return {"ok": False, "error": "missing ecommerce product id"}
        return fetch_json(args.platform_base + path + "?" + urllib.parse.urlencode({"product_id": str(product_id)}), headers=auth)

    skus = catalog("/api/v1/catalog/skus")
    packages = catalog("/api/v1/catalog/packages")
    billable_items = catalog("/api/v1/catalog/billable-items")
    rate_cards = catalog("/api/v1/catalog/rate-cards")
    offerings = fetch_json(args.platform_base + "/api/v1/catalog/offerings?" + urllib.parse.urlencode({"product_code": "ecommerce"}), headers=auth)
    assets = fetch_json(args.platform_base + "/api/v1/wallet/assets?" + urllib.parse.urlencode({"product_code": "ecommerce", "status": "active"}), headers=auth)
    quota_policies = fetch_json(args.platform_base + "/api/v1/controls/quota/policies?" + urllib.parse.urlencode({"product_code": "ecommerce"}), headers=auth)

    billable_codes = [str(x.get("code") or "") for x in items_from(billable_items)]
    rate_items = items_from(rate_cards)
    asset_items = items_from(assets)
    quota_items = items_from(quota_policies)
    offering_data = envelope_data(offerings)

    checks = {
        "platform_login": {k: v for k, v in login.items() if k != "json"},
        "template_ops_sync": {**{k: v for k, v in sync.items() if k != "json"}, "upserted_total": sync_total_from(sync)},
        "template_ops_catalog": {"ok": templates.get("ok"), "status": templates.get("status"), "total": total_from(templates), "item_count": len(template_items), "sample_refs": [i.get("template_ref") for i in template_sample]},
        "catalog_products": {"ok": products.get("ok"), "status": products.get("status"), "count": len(product_items), "ecommerce_product_id": product_id},
        "catalog_skus": {"ok": skus.get("ok"), "status": skus.get("status"), "count": count_items(skus)},
        "catalog_packages": {"ok": packages.get("ok"), "status": packages.get("status"), "count": count_items(packages)},
        "catalog_billable_items": {"ok": billable_items.get("ok"), "status": billable_items.get("status"), "count": count_items(billable_items), "codes": billable_codes},
        "catalog_rate_cards": {"ok": rate_cards.get("ok"), "status": rate_cards.get("status"), "count": len(rate_items), "target_types": sorted({str(x.get("target_type") or x.get("targetType") or "") for x in rate_items})},
        "catalog_offerings": {"ok": offerings.get("ok"), "status": offerings.get("status"), "has_payload": isinstance(offering_data, dict)},
        "wallet_assets": {"ok": assets.get("ok"), "status": assets.get("status"), "count": len(asset_items), "asset_codes": [x.get("asset_code") or x.get("assetCode") for x in asset_items]},
        "quota_policies": {"ok": quota_policies.get("ok"), "status": quota_policies.get("status"), "count": len(quota_items)},
        "token_obtained": bool(token),
    }
    expectations = {
        "platform_login_token": bool(login.get("ok") and token),
        "template_sync_request_ok": bool(sync.get("ok") and not sync.get("skipped")),
        "template_sync_upserted_non_empty": bool(sync.get("ok") and sync_total_from(sync) >= 1),
        "template_ops_persisted_projection_visible": bool(templates.get("ok") and total_from(templates) >= 1),
        "template_ops_ecommerce_non_empty": bool(templates.get("ok") and total_from(templates) >= 1 and len(template_items) >= 1),
        "template_ops_projection_fields": template_fields_ok and template_semantic_fields,
        "catalog_product_ecommerce_exists": bool(products.get("ok") and product_id),
        "catalog_skus_minimum": bool(skus.get("ok") and count_items(skus) >= 5),
        "catalog_packages_minimum": bool(packages.get("ok") and count_items(packages) >= 5),
        "catalog_billable_items_minimum": bool(billable_items.get("ok") and count_items(billable_items) >= 1 and any("ecommerce" in code for code in billable_codes)),
        "catalog_rate_cards_minimum": bool(rate_cards.get("ok") and len(rate_items) >= 6 and {"sku", "billable_item"}.issubset({str(x.get("target_type") or x.get("targetType") or "") for x in rate_items})),
        "wallet_assets_minimum": bool(assets.get("ok") and len(asset_items) >= 4),
        "quota_policies_minimum": bool(quota_policies.get("ok") and len(quota_items) >= 5),
        "offerings_payload_ecommerce": bool(offerings.get("ok") and isinstance(offering_data, dict)),
    }
    report = {
        "project": args.project,
        "feature": args.feature,
        "status": "PASS" if all(expectations.values()) else "FAIL",
        "scope": "platform-ops-visible-baseline",
        "expectations": expectations,
        "checks": checks,
        "notes": ["Password/token values are used only in memory and are never printed.", "Gate requires the Ecommerce Template Ops sync HTTP request to succeed and report non-empty upserts; persisted projection visibility is tracked separately and cannot mask sync failure."],
    }
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
