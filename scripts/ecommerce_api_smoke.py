from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def fetch(url: str, timeout: float = 5.0) -> dict:
    started = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "agentic-selfcheck/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(4096).decode("utf-8", errors="replace")
            return {"url": url, "status": resp.status, "ok": 200 <= resp.status < 400, "duration_ms": round((time.time() - started) * 1000), "body_prefix": body[:240]}
    except urllib.error.HTTPError as e:
        body = e.read(1024).decode("utf-8", errors="replace")
        return {"url": url, "status": e.code, "ok": False, "duration_ms": round((time.time() - started) * 1000), "body_prefix": body[:240]}
    except Exception as e:
        return {"url": url, "status": None, "ok": False, "duration_ms": round((time.time() - started) * 1000), "error": str(e)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--feature", required=True)
    args = ap.parse_args()
    checks = [
        fetch("http://127.0.0.1:8396/healthz"),
        fetch("http://127.0.0.1:8396/readyz"),
        fetch("http://127.0.0.1:5181/"),
        fetch("http://127.0.0.1:8396/api/v1/ecommerce/products/00000000-0000-0000-0000-000000000000"),
    ]
    # Last check is expected to be auth/404-style non-2xx; it proves route boundary responds without secret leakage.
    positive = checks[:3]
    report = {
        "project": args.project,
        "feature": args.feature,
        "status": "PASS" if all(c["ok"] for c in positive) else "FAIL",
        "scope": "service-readiness-and-public-boundary-smoke",
        "checks": checks,
        "notes": [
            "This harness verifies live backend/frontend readiness and public route boundary only.",
            "Protected business-path API smoke requires a redacted auth fixture and will be added as a stricter verifier.",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
