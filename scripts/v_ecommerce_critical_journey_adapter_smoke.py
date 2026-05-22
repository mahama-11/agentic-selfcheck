#!/usr/bin/env python3
"""Smoke-test the V/Ecommerce critical journey adapter live API flow against a local fake server.

This validates adapter behavior and redaction without coupling generic SelfCheck core to V routes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "fixture-password-should-not-leak"
TOKEN = "fixture-token-should-not-leak"
CALLS: list[tuple[str, str]] = []


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        return json.loads(raw or "{}")

    def do_POST(self) -> None:  # noqa: N802
        CALLS.append(("POST", self.path))
        if self.path == "/api/v1/ecommerce/auth/login":
            payload = self._read_json()
            if payload.get("email") == "ecom-admin@example.test" and payload.get("password") == PASSWORD:
                self._json(200, {"data": {"access_token": TOKEN}})
            else:
                self._json(401, {"error": "invalid credentials"})
            return
        if self.path == "/api/v1/ecommerce/products":
            self._json(200, {"data": {"product": {"id": "prod-smoke-1"}}})
            return
        if self.path == "/api/v1/ecommerce/products/prod-smoke-1/v2/visual-sessions":
            self._json(200, {"data": {"session": {"id": "session-smoke-1"}}})
            return
        if self.path == "/api/v1/ecommerce/assets/source":
            self._json(201, {"data": {"id": "asset-smoke-1"}})
            return
        if self.path == "/api/v1/ecommerce/products/prod-smoke-1/assets":
            self._json(200, {"data": {"id": "relation-smoke-1"}})
            return
        if self.path == "/api/v1/ecommerce/products/prod-smoke-1/listing-versions":
            self._json(200, {"data": {"id": "listing-smoke-1"}})
            return
        if self.path == "/api/v1/ecommerce/products/prod-smoke-1/listing-versions/adopt":
            self._json(200, {"data": {"success": True}})
            return
        if self.path == "/api/v1/ecommerce/products/prod-smoke-1/profit-snapshots/calculate":
            self._json(200, {"data": {"id": "profit-smoke-1"}})
            return
        if self.path == "/api/v1/ecommerce/products/prod-smoke-1/export-tasks":
            self._json(200, {"data": {"id": "export-task-smoke-1"}})
            return
        if self.path == "/api/v1/ecommerce/export-packages":
            self._json(200, {"data": {"package_id": "package-smoke-1", "succeeded": 1, "failed": 0}})
            return
        if self.path == "/api/v1/ecommerce/template-center/catalog/tpl-smoke-1/favorite":
            self._json(200, {"data": {"templateId": "tpl-smoke-1", "favorited": True}})
            return
        if self.path == "/api/v1/ecommerce/template-center/catalog/tpl-smoke-1/copy":
            self._json(200, {"data": {"templateInstanceId": "inst-smoke-1", "templateId": "tpl-smoke-1"}})
            return
        if self.path == "/api/v1/ecommerce/template-center/catalog/tpl-smoke-1/use":
            self._json(200, {"data": {"templateId": "tpl-smoke-1", "preloadedTemplatePayload": {"templateId": "tpl-smoke-1"}}})
            return
        self._json(404, {"error": "not found"})

    def do_PATCH(self) -> None:  # noqa: N802
        CALLS.append(("PATCH", self.path))
        if self.path == "/api/v1/ecommerce/products/prod-smoke-1/status":
            self._json(200, {"data": {"id": "prod-smoke-1", "status": "assets_ready"}})
            return
        self._json(404, {"error": "not found"})

    def do_GET(self) -> None:  # noqa: N802
        CALLS.append(("GET", self.path))
        if self.path == "/api/v1/ecommerce/products/prod-smoke-1":
            self._json(200, {"data": {"product": {"id": "prod-smoke-1", "sku_code": "SC-SKU-smoke"}}})
            return
        if self.path == "/api/v1/ecommerce/v2/visual-workflows/session-smoke-1/stage-view":
            self._json(200, {"data": {"stage": "prep", "large_contract_payload": "x" * 12000}})
            return
        if self.path == "/api/v1/ecommerce/downloads":
            self._json(200, {"data": [{"id": "download-smoke-1"}]})
            return
        if self.path == "/api/v1/ecommerce/template-center/catalog?locale=zh-CN&modality=image&sortBy=recommended":
            self._json(200, {"data": [{"id": "tpl-smoke-1", "name": "Smoke Template"}]})
            return
        if self.path == "/api/v1/ecommerce/template-center/catalog/facets?locale=zh-CN":
            self._json(200, {"data": {"platforms": []}})
            return
        if self.path == "/api/v1/ecommerce/template-center/catalog/tpl-smoke-1?locale=zh-CN":
            self._json(200, {"data": {"catalog": {"id": "tpl-smoke-1"}}})
            return
        if self.path in {
            "/api/v1/ecommerce/commercial/offerings",
            "/api/v1/ecommerce/wallet/summary",
            "/api/v1/ecommerce/billing/summary",
            "/api/v1/ecommerce/promotions/programs",
            "/api/v1/ecommerce/promotions/me/overview",
            "/api/v1/ecommerce/commissions/me/overview",
        }:
            self._json(200, {"data": {"ok": True}})
            return
        self._json(404, {"error": "not found"})

    def do_DELETE(self) -> None:  # noqa: N802
        CALLS.append(("DELETE", self.path))
        if self.path == "/api/v1/ecommerce/products/prod-smoke-1":
            self._json(200, {"data": {"deleted": True}})
            return
        if self.path == "/api/v1/ecommerce/template-center/catalog/tpl-smoke-1/favorite":
            self._json(200, {"data": {"templateId": "tpl-smoke-1", "favorited": False}})
            return
        self._json(404, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        fixture = tmp / "ecommerce-login.env"
        fixture.write_text(
            "\n".join([
                "PLATFORM_DEV_ADMIN_EMAIL=platform-admin@example.test",
                "PLATFORM_DEV_ADMIN_PASSWORD=wrong-platform-password",
                "ECOMMERCE_AUTH_EMAIL=ecom-admin@example.test",
                f"ECOMMERCE_AUTH_PASSWORD={PASSWORD}",
                f"ECOMMERCE_BASE_URL={base}",
            ]),
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.update({
            "SELFCHECK_PROJECT_ROOT": "/root/work/v",
            "SELFCHECK_REPORT_DIR": str(tmp / "reports"),
            "SELFCHECK_AUTH_FIXTURE": str(fixture),
            "SELFCHECK_JOURNEY_PHASE": "api",
            "ECOM_CRITICAL_JOURNEY_MODE": "live",
        })
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/adapters/v_ecommerce_critical_journey.py"), "--phase", "api"],
            text=True,
            capture_output=True,
            timeout=30,
            env=env,
            cwd=ROOT,
        )
        server.shutdown()
        combined = proc.stdout + proc.stderr
        assert proc.returncode == 0, combined
        assert PASSWORD not in combined, combined
        assert TOKEN not in combined, combined
        required_calls = {
            ("POST", "/api/v1/ecommerce/auth/login"),
            ("POST", "/api/v1/ecommerce/products"),
            ("GET", "/api/v1/ecommerce/products/prod-smoke-1"),
            ("POST", "/api/v1/ecommerce/products/prod-smoke-1/v2/visual-sessions"),
            ("GET", "/api/v1/ecommerce/v2/visual-workflows/session-smoke-1/stage-view"),
            ("POST", "/api/v1/ecommerce/assets/source"),
            ("POST", "/api/v1/ecommerce/products/prod-smoke-1/assets"),
            ("PATCH", "/api/v1/ecommerce/products/prod-smoke-1/status"),
            ("POST", "/api/v1/ecommerce/products/prod-smoke-1/listing-versions"),
            ("POST", "/api/v1/ecommerce/products/prod-smoke-1/listing-versions/adopt"),
            ("POST", "/api/v1/ecommerce/products/prod-smoke-1/profit-snapshots/calculate"),
            ("POST", "/api/v1/ecommerce/products/prod-smoke-1/export-tasks"),
            ("POST", "/api/v1/ecommerce/export-packages"),
            ("GET", "/api/v1/ecommerce/downloads"),
            ("GET", "/api/v1/ecommerce/template-center/catalog?locale=zh-CN&modality=image&sortBy=recommended"),
            ("GET", "/api/v1/ecommerce/template-center/catalog/facets?locale=zh-CN"),
            ("GET", "/api/v1/ecommerce/template-center/catalog/tpl-smoke-1?locale=zh-CN"),
            ("POST", "/api/v1/ecommerce/template-center/catalog/tpl-smoke-1/favorite"),
            ("DELETE", "/api/v1/ecommerce/template-center/catalog/tpl-smoke-1/favorite"),
            ("POST", "/api/v1/ecommerce/template-center/catalog/tpl-smoke-1/copy"),
            ("POST", "/api/v1/ecommerce/template-center/catalog/tpl-smoke-1/use"),
            ("GET", "/api/v1/ecommerce/commercial/offerings"),
            ("GET", "/api/v1/ecommerce/wallet/summary"),
            ("GET", "/api/v1/ecommerce/billing/summary"),
            ("GET", "/api/v1/ecommerce/promotions/programs"),
            ("GET", "/api/v1/ecommerce/promotions/me/overview"),
            ("GET", "/api/v1/ecommerce/commissions/me/overview"),
            ("DELETE", "/api/v1/ecommerce/products/prod-smoke-1"),
        }
        missing = required_calls - set(CALLS)
        assert not missing, f"missing calls: {sorted(missing)}; got {CALLS}"
    print("PASS: v ecommerce critical journey adapter live API smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
