#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from prototype_path_utils import resolve_under

REQUIRED_DELTA_FIELDS = [
    "previous_foundation_version",
    "candidate_foundation_version",
    "strengthened",
    "unchanged",
    "weakened",
    "foundation_evidence",
]


def finding(severity: str, path: str, message: str) -> dict:
    return {"severity": severity, "path": path, "message": message}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_kv(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    key: str | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#") or raw.strip() == "```yaml" or raw.strip() == "```":
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", raw.rstrip())
        if m:
            key = m.group(1)
            data[key] = m.group(2).strip()
            continue
        if key and re.match(r"^\s*-\s+", raw):
            item = re.sub(r"^\s*-\s+", "", raw).strip()
            data[key] = (data.get(key, "") + "\n" + item).strip()
    return data


def meaningful(v: str | None) -> bool:
    if v is None:
        return False
    s = v.strip().strip("[]").lower()
    return bool(s) and s not in {"todo", "tbd", "none", "n/a", "na", "-", "[]"}


def current_foundation_version(ledger_text: str) -> str | None:
    m = re.search(r"^current_foundation_version:\s*(\S+)\s*$", ledger_text, flags=re.M)
    return m.group(1) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate progressive foundation-growth loop for prototype iterations.")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--delta", help="Candidate growth delta file, relative to workflow or absolute")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()
    workflow = Path(args.workflow).resolve()
    findings: list[dict] = []
    ledger = workflow / "FOUNDATION_LEDGER.md"
    if not ledger.exists() or ledger.stat().st_size < 80:
        findings.append(finding("error", str(ledger), "FOUNDATION_LEDGER.md missing or empty"))
        ledger_text = ""
    else:
        ledger_text = read(ledger)
    current = current_foundation_version(ledger_text) if ledger_text else None
    if not current:
        findings.append(finding("error", str(ledger), "current_foundation_version missing"))
    data: dict[str, str] = {}
    if args.delta:
        try:
            delta = resolve_under(workflow, args.delta, "delta")
        except ValueError as exc:
            delta = workflow / "<invalid-delta-path>"
            findings.append(finding("error", str(workflow), str(exc)))
        if not delta.exists() or delta.stat().st_size < 40:
            findings.append(finding("error", str(delta), "foundation growth delta missing or empty"))
        else:
            data = parse_kv(read(delta))
            for field in REQUIRED_DELTA_FIELDS:
                if field == "weakened":
                    if field not in data:
                        findings.append(finding("error", str(delta), "required field missing: weakened"))
                    continue
                if not meaningful(data.get(field)):
                    findings.append(finding("error", str(delta), f"required field missing or placeholder: {field}"))
            if current and data.get("previous_foundation_version") and data.get("previous_foundation_version") != current:
                findings.append(finding("error", str(delta), f"previous_foundation_version must equal current ledger version {current}"))
            if data.get("candidate_foundation_version") == data.get("previous_foundation_version"):
                findings.append(finding("error", str(delta), "candidate_foundation_version must advance beyond previous version"))
            weakened = data.get("weakened", "")
            accepted = data.get("accepted_tradeoff", "") or data.get("human_accepted_tradeoff", "")
            if meaningful(weakened) and "none" not in weakened.lower() and not meaningful(accepted):
                findings.append(finding("error", str(delta), "weakened foundation requires accepted_tradeoff"))
    result = {
        "status": "PASS" if not any(f["severity"] == "error" for f in findings) else "FAIL",
        "workflow": str(workflow),
        "current_foundation_version": current,
        "delta": data,
        "findings": findings,
    }
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']} current_foundation_version={current} findings={len(findings)}")
        for f in findings:
            print(f"{f['severity'].upper()}: {f['path']}: {f['message']}")
    return 0 if result["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
