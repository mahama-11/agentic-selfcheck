#!/usr/bin/env python3
"""Deterministic GitHub webhook receiver for Agentic SelfCheck PR autonomy.

This service intentionally keeps secrets out of the repository. Configure with env:
- GITHUB_PR_AUTONOMY_WEBHOOK_SECRET: GitHub webhook HMAC secret.
- GITHUB_PR_AUTONOMY_ROOT: repo root, default cwd.
- GITHUB_PR_AUTONOMY_HOST: default 0.0.0.0.
- GITHUB_PR_AUTONOMY_PORT: default 8655.
- GITHUB_PR_AUTONOMY_APPLY: true/false, default true.
- GITHUB_PR_AUTONOMY_ALLOW_MERGE: true/false, default false.
- GH_CONFIG_DIR: optional gh config dir for the mahama-11 account.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT_FOR_IMPORT = Path(__file__).resolve().parents[1]
if str(ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(ROOT_FOR_IMPORT))

from selfcheck.pr_autonomy import dispatch_payload  # noqa: E402

REDACT_KEYS = ("secret", "token", "password", "authorization", "api_key", "apikey", "key")


def bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if any(s in str(k).lower() for s in REDACT_KEYS):
                out[k] = "[REDACTED]"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def run(cmd: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)


def gh_json(root: Path, args: list[str], default: Any) -> Any:
    cp = run(["gh", *args], root, timeout=120)
    if cp.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args)} failed: {cp.stderr[-500:]}")
    text = cp.stdout.strip()
    if not text:
        return default
    return json.loads(text)


def normalize_check_conclusion(status: str | None, conclusion: str | None) -> str:
    status_l = (status or "").lower()
    conclusion_l = (conclusion or "").lower()
    if status_l != "completed":
        return status_l or "pending"
    return conclusion_l or "success"


def collect_check_runs(root: Path, repo: str, sha: str) -> dict[str, str]:
    if not sha:
        return {}
    data = gh_json(root, ["api", f"repos/{repo}/commits/{sha}/check-runs", "--jq", ".check_runs"], [])
    checks: dict[str, str] = {}
    for item in data or []:
        name = str(item.get("name") or "")
        if name:
            checks[name] = normalize_check_conclusion(item.get("status"), item.get("conclusion"))
    # Legacy statuses can still be used by some checks.
    try:
        statuses = gh_json(root, ["api", f"repos/{repo}/commits/{sha}/status", "--jq", ".statuses"], [])
        for item in statuses or []:
            context = str(item.get("context") or "")
            if context and context not in checks:
                checks[context] = str(item.get("state") or "").lower()
    except Exception:
        pass
    return checks


def collect_pr_files(root: Path, repo: str, number: int) -> list[str]:
    data = gh_json(root, ["api", f"repos/{repo}/pulls/{number}/files", "--paginate"], [])
    return [str(item.get("filename")) for item in data or [] if item.get("filename")]


def get_pr(root: Path, repo: str, number: int) -> dict[str, Any]:
    return gh_json(root, ["api", f"repos/{repo}/pulls/{number}"], {})


def prs_for_commit(root: Path, repo: str, sha: str) -> list[dict[str, Any]]:
    if not sha:
        return []
    cp = run([
        "gh", "api", f"repos/{repo}/commits/{sha}/pulls",
        "-H", "Accept: application/vnd.github+json",
    ], root, timeout=120)
    if cp.returncode != 0 or not cp.stdout.strip():
        return []
    return json.loads(cp.stdout)


def enrich_pull_request_payload(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    repo_obj = payload.get("repository") or {}
    repo = repo_obj.get("full_name") or f"{(repo_obj.get('owner') or {}).get('login','')}/{repo_obj.get('name','')}"
    pr_obj = payload.get("pull_request") or {}
    number = int(pr_obj.get("number") or payload.get("number") or 0)
    if not repo or not number:
        return payload
    pr = get_pr(root, repo, number)
    sha = (((pr.get("head") or {}).get("sha")) or ((pr_obj.get("head") or {}).get("sha")) or payload.get("head_sha") or "")
    enriched = dict(payload)
    enriched["repository"] = pr.get("base", {}).get("repo") or repo_obj
    enriched["pull_request"] = pr or pr_obj
    enriched["changed_files"] = collect_pr_files(root, repo, number)
    enriched["check_runs"] = collect_check_runs(root, repo, sha)
    enriched["head_sha"] = sha
    enriched["labels"] = [str(x.get("name")) for x in (pr.get("labels") or []) if x.get("name")]
    return enriched


def payload_from_workflow_run(root: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    repo_obj = payload.get("repository") or {}
    repo = repo_obj.get("full_name") or f"{(repo_obj.get('owner') or {}).get('login','')}/{repo_obj.get('name','')}"
    wr = payload.get("workflow_run") or {}
    prs = wr.get("pull_requests") or []
    sha = wr.get("head_sha") or ""
    if prs:
        number = int(prs[0].get("number") or 0)
    else:
        linked = prs_for_commit(root, repo, sha)
        number = int((linked[0] or {}).get("number") or 0) if linked else 0
    if not repo or not number:
        return None
    pr = get_pr(root, repo, number)
    synthetic = {
        "action": "synchronize",
        "repository": pr.get("base", {}).get("repo") or repo_obj,
        "pull_request": pr,
        "number": number,
        "source_event": "workflow_run",
        "workflow_run": {
            "id": wr.get("id"),
            "name": wr.get("name"),
            "status": wr.get("status"),
            "conclusion": wr.get("conclusion"),
            "head_sha": sha,
        },
    }
    return enrich_pull_request_payload(root, synthetic)


def payload_from_check_run(root: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    repo_obj = payload.get("repository") or {}
    repo = repo_obj.get("full_name") or f"{(repo_obj.get('owner') or {}).get('login','')}/{repo_obj.get('name','')}"
    cr = payload.get("check_run") or {}
    prs = cr.get("pull_requests") or []
    sha = ((cr.get("check_suite") or {}).get("head_sha") or cr.get("head_sha") or "")
    if prs:
        number = int(prs[0].get("number") or 0)
    else:
        linked = prs_for_commit(root, repo, sha)
        number = int((linked[0] or {}).get("number") or 0) if linked else 0
    if not repo or not number:
        return None
    pr = get_pr(root, repo, number)
    synthetic = {
        "action": "synchronize",
        "repository": pr.get("base", {}).get("repo") or repo_obj,
        "pull_request": pr,
        "number": number,
        "source_event": "check_run",
        "check_run": {"id": cr.get("id"), "name": cr.get("name"), "status": cr.get("status"), "conclusion": cr.get("conclusion"), "head_sha": sha},
    }
    return enrich_pull_request_payload(root, synthetic)


def enrich_payload(root: Path, event: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if event == "pull_request":
        # Label churn can be generated by this service itself; treating it as an
        # unsupported PR action creates an automation loop. Ignore it at the
        # receiver boundary while still blocking truly unexpected PR actions in
        # the policy engine when they are intentionally dispatched.
        if str(payload.get("action") or "") in {"labeled", "unlabeled", "closed"}:
            return None
        return enrich_pull_request_payload(root, payload)
    if event == "workflow_run":
        return payload_from_workflow_run(root, payload)
    if event == "check_run":
        return payload_from_check_run(root, payload)
    return None


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redact(data), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def handle_event(root: Path, event: str, delivery: str, payload: dict[str, Any], apply: bool, allow_merge: bool, allow_repair: bool) -> dict[str, Any]:
    event_id = f"{int(time.time())}-{delivery or uuid.uuid4().hex}"
    reports_dir = root / "reports" / "github-pr-autonomy-live-webhook"
    raw_path = reports_dir / "events" / f"{event_id}.raw.redacted.json"
    enriched_path = reports_dir / "events" / f"{event_id}.enriched.json"
    result_path = reports_dir / "reports" / f"{event_id}.report.json"
    write_json(raw_path, {"event": event, "delivery": delivery, "payload": payload})
    enriched = enrich_payload(root, event, payload)
    if enriched is None:
        result = {"status": "IGNORED", "event": event, "delivery": delivery, "reason": "event is not mapped to an open PR"}
        write_json(result_path, result)
        return result
    write_json(enriched_path, enriched)

    repo_obj = enriched.get("repository") or {}
    repo = repo_obj.get("full_name") or f"{(repo_obj.get('owner') or {}).get('login','')}/{repo_obj.get('name','')}"
    pr_number = int(((enriched.get("pull_request") or {}).get("number")) or enriched.get("number") or 0)

    # Run SelfCheck event route first for audit/evidence semantics.
    trigger = run([
        "python3", "-m", "selfcheck", "trigger", "--root", ".",
        "--event", "github.pull_request", "--route", "github-pr-autonomy",
        "--source", "hermes-webhook", "--payload-file", str(enriched_path), "--timeout", "300",
    ], root, timeout=360)

    # Reporter owns GitHub write-back and optional merge gate.
    report_rel = str(result_path.relative_to(root))
    cmd = [
        "python3", "scripts/github_pr_autonomy_report.py",
        "--root", ".", "--payload-file", str(enriched_path),
        "--repo", repo, "--pr", str(pr_number), "--report", report_rel,
    ]
    if apply:
        cmd.append("--apply")
        cmd.append("--labels")
    if allow_merge:
        cmd.append("--allow-merge")
    reporter = run(cmd, root, timeout=240)

    repair = None
    if allow_repair and reporter.returncode == 0:
        try:
            report_data = json.loads(result_path.read_text(encoding="utf-8"))
            decision = report_data.get("decision") or {}
        except Exception:
            decision = {}
        if decision.get("state") == "NEEDS_REPAIR" and "CREATE_REPAIR_DISPATCH" in (decision.get("actions") or []):
            repair_rel = str((reports_dir / "repairs" / f"{event_id}.repair.json").relative_to(root))
            repair_cmd = [
                "python3", "scripts/github_pr_autonomy_repair.py",
                "--root", ".", "--repo", repo, "--pr", str(pr_number),
                "--expected-sha", str(decision.get("head_sha") or ""),
                "--report", repair_rel,
            ]
            repair_cp = run(repair_cmd, root, timeout=600)
            repair = {
                "exit_code": repair_cp.returncode,
                "stdout_tail": repair_cp.stdout[-2000:],
                "stderr_tail": repair_cp.stderr[-1000:],
                "report_path": str(root / repair_rel),
            }

    result = {
        "status": "PASS" if trigger.returncode == 0 and reporter.returncode == 0 and (repair is None or repair.get("exit_code") == 0) else "FAIL",
        "event": event,
        "delivery": delivery,
        "repo": repo,
        "pr": pr_number,
        "trigger_exit_code": trigger.returncode,
        "reporter_exit_code": reporter.returncode,
        "trigger_stdout_tail": trigger.stdout[-2000:],
        "trigger_stderr_tail": trigger.stderr[-1000:],
        "reporter_stdout_tail": reporter.stdout[-2000:],
        "reporter_stderr_tail": reporter.stderr[-1000:],
        "repair": repair,
        "raw_path": str(raw_path),
        "enriched_path": str(enriched_path),
        "report_path": str(result_path),
    }
    if result["status"] != "PASS":
        write_json(result_path.with_suffix(".failure.json"), result)
    return result


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "AgenticSelfCheckGitHubWebhook/1.0"

    def _json(self, code: int, data: dict[str, Any]) -> None:
        body = json.dumps(redact(data), ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/health":
            self._json(200, {"status": "ok", "service": "github-pr-autonomy-webhook"})
        else:
            self._json(404, {"status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in {"/github-pr-autonomy", "/webhooks/github-pr-autonomy"}:
            self._json(404, {"status": "not_found"})
            return
        length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(length)
        secret = self.server.webhook_secret  # type: ignore[attr-defined]
        if secret:
            sig = self.headers.get("X-Hub-Signature-256") or ""
            expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(sig, expected):
                self._json(401, {"status": "unauthorized", "reason": "signature mismatch"})
                return
        event = self.headers.get("X-GitHub-Event") or ""
        delivery = self.headers.get("X-GitHub-Delivery") or uuid.uuid4().hex
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:
            self._json(400, {"status": "bad_request", "reason": str(exc)})
            return
        try:
            result = handle_event(self.server.root, event, delivery, payload, self.server.apply, self.server.allow_merge, self.server.allow_repair)  # type: ignore[attr-defined]
            self._json(200 if result.get("status") in {"PASS", "IGNORED"} else 500, result)
        except Exception as exc:
            self._json(500, {"status": "FAIL", "reason": str(exc)})


class ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=os.getenv("GITHUB_PR_AUTONOMY_ROOT", str(ROOT_FOR_IMPORT)))
    parser.add_argument("--host", default=os.getenv("GITHUB_PR_AUTONOMY_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("GITHUB_PR_AUTONOMY_PORT", "8655")))
    parser.add_argument("--apply", action="store_true", default=bool_env("GITHUB_PR_AUTONOMY_APPLY", True))
    parser.add_argument("--allow-merge", action="store_true", default=bool_env("GITHUB_PR_AUTONOMY_ALLOW_MERGE", False))
    parser.add_argument("--allow-repair", action="store_true", default=bool_env("GITHUB_PR_AUTONOMY_ALLOW_REPAIR", False))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    secret = os.getenv("GITHUB_PR_AUTONOMY_WEBHOOK_SECRET", "")
    if not secret:
        print("GITHUB_PR_AUTONOMY_WEBHOOK_SECRET is required", file=sys.stderr)
        return 2
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.root = root  # type: ignore[attr-defined]
    server.webhook_secret = secret  # type: ignore[attr-defined]
    server.apply = args.apply  # type: ignore[attr-defined]
    server.allow_merge = args.allow_merge  # type: ignore[attr-defined]
    server.allow_repair = args.allow_repair  # type: ignore[attr-defined]
    print(json.dumps({"status": "listening", "host": args.host, "port": args.port, "root": str(root), "apply": args.apply, "allow_merge": args.allow_merge, "allow_repair": args.allow_repair}, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
