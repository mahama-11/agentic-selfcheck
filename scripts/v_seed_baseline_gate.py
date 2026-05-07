#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


REQUIRED_ROLE_GRANTS = {
    "owner": {"billing.read", "billing.write", "oauth.read", "oauth.write", "logs.read", "platform.admin"},
    "admin": {"billing.read", "billing.write", "oauth.read", "oauth.write", "logs.read"},
    "developer": {"org.read", "org.switch", "team.read", "org.usage.read"},
    "viewer": {"org.read", "org.switch", "team.read"},
}
FORBIDDEN_ROLE_GRANTS = {
    "admin": {"platform.admin"},
    "developer": {"billing.read", "billing.write", "oauth.read", "oauth.write", "platform.admin"},
    "viewer": {"billing.read", "billing.write", "logs.read", "oauth.read", "oauth.write", "platform.admin"},
}


def fetch_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 5.0) -> dict[str, Any]:
    started = time.time()
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req_headers = {"User-Agent": "agentic-selfcheck/seed-baseline/0.2"}
    if body is not None:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(1048576).decode("utf-8", errors="replace")
            try:
                parsed: Any = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = {"body_prefix": raw[:240], "parse_error": "json_decode"}
            return {"url": url, "status": resp.status, "ok": 200 <= resp.status < 400, "duration_ms": round((time.time() - started) * 1000), "json": parsed}
    except urllib.error.HTTPError as e:
        raw = e.read(2048).decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"body_prefix": raw[:240]}
        return {"url": url, "status": e.code, "ok": False, "duration_ms": round((time.time() - started) * 1000), "json": parsed}
    except Exception as e:
        return {"url": url, "status": None, "ok": False, "duration_ms": round((time.time() - started) * 1000), "error": str(e)}


def psql_value(container: str, user: str, database: str, sql: str, *, timeout: int = 10) -> dict[str, Any]:
    cmd = ["docker", "exec", container, "psql", "-U", user, "-d", database, "-Atc", sql]
    started = time.time()
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    value = proc.stdout.strip()
    return {"ok": proc.returncode == 0, "value": value, "duration_ms": round((time.time() - started) * 1000), "stderr": proc.stderr.strip()[:240]}


def psql_count(container: str, user: str, database: str, sql: str) -> dict[str, Any]:
    out = psql_value(container, user, database, sql)
    value = str(out.get("value", "")).strip()
    out["ok"] = bool(out.get("ok")) and value.isdigit()
    out["value"] = int(value) if value.isdigit() else value
    return out


def psql_json(container: str, user: str, database: str, sql: str) -> dict[str, Any]:
    out = psql_value(container, user, database, sql)
    try:
        out["json"] = json.loads(out.get("value") or "{}")
    except json.JSONDecodeError:
        out["json"] = {}
        out["ok"] = False
    return out


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


def catalog_items(resp: dict[str, Any]) -> list[dict[str, Any]]:
    data = envelope_data(resp)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        raw = data.get("items") or data.get("list") or data.get("data")
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    return []


def role_grant_expectations(role_json: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    details: dict[str, Any] = {}
    ok = True
    for role, expected in REQUIRED_ROLE_GRANTS.items():
        actual = set(role_json.get(role) or [])
        missing = sorted(expected - actual)
        forbidden_present = sorted(FORBIDDEN_ROLE_GRANTS.get(role, set()) & actual)
        details[role] = {"count": len(actual), "missing_required": missing, "forbidden_present": forbidden_present}
        ok = ok and not missing and not forbidden_present
    return ok, details


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="v-ecommerce-worktree")
    ap.add_argument("--feature", default="dev-seed-baseline")
    ap.add_argument("--platform-base", default="http://127.0.0.1:8195")
    ap.add_argument("--ecommerce-base", default="http://127.0.0.1:8396")
    ap.add_argument("--email", default=os.environ.get("PLATFORM_DEV_ADMIN_EMAIL", "admin@verilocale.com"))
    ap.add_argument("--password-env", default="PLATFORM_DEV_ADMIN_PASSWORD")
    args = ap.parse_args()

    password = os.environ.get(args.password_env, "123qwe")
    login = fetch_json(args.platform_base + "/api/v1/auth/login", method="POST", payload={"email": args.email, "password": password})
    token = extract_token(login)
    auth_headers = {"Authorization": "Bearer " + token} if token else {}

    role_sql = """
      select coalesce(json_object_agg(role_id, permissions), '{}'::json)
      from (
        select role_id, json_agg(permission_id order by permission_id) as permissions
        from role_permissions
        where role_id in ('owner','admin','developer','viewer')
        group by role_id
      ) rp;
    """
    role_grants = psql_json("tips-postgres", "tips_user", "platform", role_sql)
    role_ok, role_details = role_grant_expectations(role_grants.get("json") if isinstance(role_grants.get("json"), dict) else {})

    catalog_url = args.ecommerce_base + "/api/v1/ecommerce/template-center/catalog?" + urllib.parse.urlencode({"scope": "official", "locale": "zh", "limit": 8})
    template_catalog = fetch_json(catalog_url)
    items = catalog_items(template_catalog)
    first_template = items[0] if items else {}
    template_id = first_template.get("id") or first_template.get("templateId") or first_template.get("template_id")

    detail = fetch_json(args.ecommerce_base + "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(str(template_id)) + "?locale=zh") if template_id else {"ok": False, "error": "no template id from catalog"}
    use = fetch_json(args.ecommerce_base + "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(str(template_id)) + "/use", method="POST", headers=auth_headers) if template_id and token else {"ok": False, "error": "missing token or template id"}
    favorite = fetch_json(args.ecommerce_base + "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(str(template_id)) + "/favorite", method="POST", headers=auth_headers) if template_id and token else {"ok": False, "error": "missing token or template id"}
    copy = fetch_json(args.ecommerce_base + "/api/v1/ecommerce/template-center/catalog/" + urllib.parse.quote(str(template_id)) + "/copy", method="POST", headers=auth_headers) if template_id and token else {"ok": False, "error": "missing token or template id"}

    detail_data = envelope_data(detail)
    use_data = envelope_data(use)
    copy_data = envelope_data(copy)
    favorite_data = envelope_data(favorite)
    catalog_content_ok = bool(items and template_id and (first_template.get("name") or first_template.get("summary") or first_template.get("slug")))
    detail_content_ok = bool(isinstance(detail_data, dict) and (detail_data.get("catalog") or {}).get("id") == template_id)
    use_content_ok = bool(isinstance(use_data, dict) and (use_data.get("targetRoute") or use_data.get("target_route") or use_data.get("toolSlug") or use_data.get("tool_slug")))
    favorite_content_ok = bool(favorite.get("ok") and (not isinstance(favorite_data, dict) or favorite_data.get("favorited") is not False))
    copy_content_ok = bool(copy.get("ok") and isinstance(copy_data, dict) and (copy_data.get("templateInstanceId") or copy_data.get("template_instance_id") or copy_data.get("id")))

    checks = {
        "platform_login": {k: v for k, v in login.items() if k != "json"},
        "platform_admin_rows": psql_count("tips-postgres", "tips_user", "platform", "select count(*) from users where lower(email)=lower('admin@verilocale.com') and is_platform_admin=true and status='active';"),
        "platform_permissions": psql_count("tips-postgres", "tips_user", "platform", "select count(*) from permissions;"),
        "platform_role_grants": {"ok": role_grants.get("ok"), "duration_ms": role_grants.get("duration_ms"), "roles": role_details},
        "ecommerce_local_template_catalogs": psql_count("tips-postgres", "tips_user", "ecommerce", "select count(*) from ecommerce_template_catalogs where scope='official' and managed_source='seed_builtin';"),
        "ecommerce_template_catalog_api": {"ok": template_catalog.get("ok"), "status": template_catalog.get("status"), "duration_ms": template_catalog.get("duration_ms"), "item_count": len(items), "first_template_id": template_id},
        "ecommerce_template_detail_api": {"ok": detail.get("ok"), "status": detail.get("status"), "duration_ms": detail.get("duration_ms")},
        "ecommerce_template_use_api": {"ok": use.get("ok"), "status": use.get("status"), "duration_ms": use.get("duration_ms")},
        "ecommerce_template_favorite_api": {"ok": favorite.get("ok"), "status": favorite.get("status"), "duration_ms": favorite.get("duration_ms")},
        "ecommerce_template_copy_api": {"ok": copy.get("ok"), "status": copy.get("status"), "duration_ms": copy.get("duration_ms")},
        "token_obtained": bool(token),
    }
    expectations = {
        "platform_login_token": login.get("ok") is True and bool(token),
        "platform_admin_rows": checks["platform_admin_rows"].get("value") == 1,
        "platform_permissions_include_expected": int(checks["platform_permissions"].get("value") or 0) >= 15,
        "platform_role_grants_semantic": role_ok,
        "ecommerce_local_template_catalogs": int(checks["ecommerce_local_template_catalogs"].get("value") or 0) >= 100,
        "ecommerce_catalog_content": template_catalog.get("ok") is True and catalog_content_ok,
        "ecommerce_detail_content": detail.get("ok") is True and detail_content_ok,
        "ecommerce_use_content": use.get("ok") is True and use_content_ok,
        "ecommerce_favorite_content": favorite_content_ok,
        "ecommerce_copy_content": copy_content_ok,
    }
    report = {
        "project": args.project,
        "feature": args.feature,
        "status": "PASS" if all(expectations.values()) else "FAIL",
        "scope": "platform-common-and-ecommerce-business-dev-seed-baseline",
        "expectations": expectations,
        "checks": checks,
        "notes": [
            "Password/token values are used only in memory and are never printed.",
            "RBAC gate is semantic rather than role_permissions row-count based.",
            "Ecommerce gate validates catalog list, detail, favorite, copy, and use on a returned template.",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
