from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen


def check_url(url: str) -> bool:
    try:
        with urlopen(url, timeout=5) as r:
            return 200 <= r.status < 400
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--feature", required=True)
    args = ap.parse_args()

    reports_dir = Path("reports") / args.feature / "browser-artifacts"
    reports_dir.mkdir(parents=True, exist_ok=True)
    screenshot = reports_dir / "frontend-login.png"
    dom = reports_dir / "frontend-login.dom.html"
    url = "http://127.0.0.1:5181/login"
    started = time.time()
    frontend_ok = check_url("http://127.0.0.1:5181/")
    cmd = [
        "/usr/bin/chromium",
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--window-size=1440,1000",
        "--virtual-time-budget=7000",
        f"--screenshot={screenshot}",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    dump = subprocess.run([
        "/usr/bin/chromium",
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        "--virtual-time-budget=7000",
        "--dump-dom",
        url,
    ], capture_output=True, text=True, timeout=60)
    dom.write_text(dump.stdout[-200000:], encoding="utf-8")
    dom_text = dump.stdout.lower()
    assertions = {
        "frontend_root_200": frontend_ok,
        "screenshot_exists": screenshot.exists() and screenshot.stat().st_size > 1000,
        "dom_contains_login_surface": any(x in dom_text for x in ["login", "登录", "email", "password"]),
    }
    status = "PASS" if proc.returncode == 0 and all(assertions.values()) else "FAIL"
    report = {
        "project": args.project,
        "feature": args.feature,
        "status": status,
        "scope": "headless-browser-login-surface-smoke",
        "url": url,
        "duration_seconds": round(time.time() - started, 3),
        "assertions": assertions,
        "artifacts": {"screenshot": str(screenshot), "dom": str(dom)},
        "stdout_tail": (proc.stdout + dump.stdout)[-1200:],
        "stderr_tail": (proc.stderr + dump.stderr)[-1200:],
        "notes": [
            "This is a real headless Chromium smoke, not full authenticated product pipeline E2E.",
            "Full pipeline browser verifier requires auth fixture and generated-asset callback fixture.",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
