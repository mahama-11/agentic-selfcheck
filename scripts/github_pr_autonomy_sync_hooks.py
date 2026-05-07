#!/usr/bin/env python3
"""Sync V workspace GitHub hooks to the current PR autonomy tunnel URL.

Reads the webhook secret from env (repo-external), parses the latest cloudflared
trycloudflare URL from the tunnel log, and upserts the webhook on the allowlisted
repositories. Intended for systemd timer/watchdog use.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPOS = [
    "mahama-11/platform-backend",
    "mahama-11/ecommerce-backend",
    "mahama-11/platform-frontend",
    "mahama-11/ecommerce-frontend",
]
EVENTS = ["pull_request", "workflow_run", "check_run"]
DIRECT_IP_URL = "http://51.68.227.243:8655/github-pr-autonomy"


def run(args: list[str], input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=input_text, text=True, capture_output=True, timeout=120)


def latest_tunnel_url(log_path: Path) -> str:
    text = log_path.read_text(errors="ignore") if log_path.exists() else ""
    urls = re.findall(r"https://[-a-zA-Z0-9]+\.trycloudflare\.com", text)
    if not urls:
        raise SystemExit(f"no trycloudflare URL found in {log_path}")
    return urls[-1].rstrip("/") + "/github-pr-autonomy"


def gh_json(args: list[str]) -> object:
    cp = run(["gh", *args])
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr[-500:])
    return json.loads(cp.stdout or "null")


def hook_ids(repo: str, url: str) -> list[int]:
    data = gh_json(["api", f"repos/{repo}/hooks"])
    return [int(x["id"]) for x in data if (x.get("config") or {}).get("url") == url]


def upsert(repo: str, url: str, secret: str) -> dict:
    payload = json.dumps({
        "name": "web",
        "active": True,
        "events": EVENTS,
        "config": {"url": url, "content_type": "json", "secret": secret, "insecure_ssl": "0"},
    })
    current = hook_ids(repo, url)
    for old in hook_ids(repo, DIRECT_IP_URL):
        run(["gh", "api", "--method", "DELETE", f"repos/{repo}/hooks/{old}"])
    if current:
        hook_id = current[0]
        cp = run(["gh", "api", "--method", "PATCH", f"repos/{repo}/hooks/{hook_id}", "--input", "-"], payload)
    else:
        cp = run(["gh", "api", "--method", "POST", f"repos/{repo}/hooks", "--input", "-"], payload)
    if cp.returncode != 0:
        return {"repo": repo, "status": "FAIL", "stderr_tail": cp.stderr[-500:]}
    data = json.loads(cp.stdout)
    return {"repo": repo, "status": "PASS", "hook_id": data.get("id"), "url": (data.get("config") or {}).get("url"), "events": data.get("events")}


def main() -> int:
    secret = os.getenv("GITHUB_PR_AUTONOMY_WEBHOOK_SECRET")
    if not secret:
        print("GITHUB_PR_AUTONOMY_WEBHOOK_SECRET is required", file=sys.stderr)
        return 2
    log_path = Path(os.getenv("GITHUB_PR_AUTONOMY_TUNNEL_LOG", "/root/.hermes/logs/agentic-selfcheck-github-webhook-tunnel.log"))
    url = latest_tunnel_url(log_path)
    results = [upsert(repo, url, secret) for repo in REPOS]
    out = {"status": "PASS" if all(r.get("status") == "PASS" for r in results) else "FAIL", "url": url, "results": results}
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if out["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
