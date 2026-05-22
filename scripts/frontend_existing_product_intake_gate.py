#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

REQUIRED = [
    "PROJECT_CONTEXT.md",
    "EXISTING_PRODUCT_BASELINE.md",
    "API_BACKEND_FEASIBILITY_MAP.md",
    "PRODUCT_SURFACE_LANGUAGE_RULES.md",
    "PROTOTYPE_REQUIREMENT_TRACE.md",
]
TEMPLATE_DIR = Path("templates/frontend/existing-product-intake")
BANNED_VISIBLE_TERMS = [
    "V1", "V2", "V3", "Stage", "contract-needed", "backend gap", "API gap",
    "gate", "verifier", "coverage", "selfcheck", "model provider", "GPU", "TFlops",
    "Stable Diffusion", "AI 推理引擎在线", "Test001", "Test002", "Test003",
    "Execution Sandbox", "Reactive Decision Tree", "Dual-Track Extraction",
    "当前成熟度", "评审通过", "暴露问题",
]
PLACEHOLDER_RE = re.compile(r"\b(Fill|TODO|TBD|N/A|placeholder|example\.png)\b|填写|待补", re.I)


def finding(severity: str, path: Path | str, message: str) -> dict[str, str]:
    return {"severity": severity, "path": str(path), "message": message}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except Exception:
        return False


def path_has_symlink(path: Path, stop: Path) -> bool:
    stop = stop.resolve()
    cur = path
    chain = [cur]
    while cur != stop and cur != cur.parent:
        cur = cur.parent
        chain.append(cur)
    return any(p.is_symlink() for p in chain)


def resolve_workflow(root: Path, raw: str) -> Path:
    wf = Path(raw)
    if not wf.is_absolute():
        wf = root / wf
    resolved = wf.resolve()
    governed = (root / ".hermes/workflows").resolve()
    if not is_within(resolved, governed):
        raise ValueError("workflow must stay under governed .hermes/workflows")
    if path_has_symlink(wf, governed) or any(p.is_symlink() for p in resolved.rglob("*")):
        raise ValueError("workflow and intake artifacts must not be symlinked")
    return resolved


def nonempty(path: Path, min_bytes: int = 120) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size >= min_bytes


def table_rows(text: str, min_cols: int = 4) -> int:
    rows = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|") or "---" in line:
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) >= min_cols and sum(bool(c) for c in cols) >= min_cols:
            if not re.search(r"Requirement|Route|Visible user function|Internal concept|Product surface", line, re.I):
                rows += 1
    return rows


def strip_html(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def visible_text(text: str) -> str:
    attrs = []
    for attr in ("alt", "title", "aria-label", "placeholder", "value"):
        attrs.extend(re.findall(rf"\b{attr}\s*=\s*['\"]([^'\"]+)['\"]", text, flags=re.I))
    text_nodes = strip_html(text)
    return re.sub(r"\s+", " ", " ".join([text_nodes, *attrs])).strip()


def banned_term_present(term: str, visible: str) -> bool:
    if re.fullmatch(r"[A-Za-z0-9]+", term):
        return re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", visible, flags=re.I) is not None
    pattern = re.escape(term).replace(r"\ ", r"\s+")
    return re.search(pattern, visible, flags=re.I) is not None


def check_templates(root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for name in REQUIRED[1:]:
        path = root / TEMPLATE_DIR / name
        if not nonempty(path):
            findings.append(finding("error", path, "required existing-product intake template missing or empty"))
    return findings


def check_text_artifact(wf: Path, rel: str, markers: list[str], *, min_rows: int = 0, min_cols: int = 4, min_bytes: int = 220) -> list[dict[str, str]]:
    path = wf / rel
    findings: list[dict[str, str]] = []
    if not nonempty(path, min_bytes):
        return [finding("error", path, "required existing-product intake artifact missing or too thin")]
    text = read(path)
    for marker in markers:
        if marker not in text:
            findings.append(finding("error", path, f"missing required section/field: {marker}"))
    if PLACEHOLDER_RE.search(text):
        findings.append(finding("error", path, "artifact contains placeholders/TODOs"))
    if min_rows and table_rows(text, min_cols) < min_rows:
        findings.append(finding("error", path, f"requires at least {min_rows} concrete table rows"))
    return findings


def check_workflow(root: Path, workflow_raw: str, risk: str) -> dict[str, Any]:
    try:
        wf = resolve_workflow(root, workflow_raw)
    except ValueError as exc:
        return {"status": "FAIL", "workflow": workflow_raw, "findings": [finding("error", workflow_raw, str(exc))]}
    findings: list[dict[str, str]] = []
    findings.extend(check_text_artifact(wf, "PROJECT_CONTEXT.md", [
        "Existing product background",
        "Current implementation state",
        "Current visual and interaction baseline",
        "System feasibility map",
        "User-facing product UI boundary",
        "Prototype grounding rule",
    ], min_rows=0))
    findings.extend(check_text_artifact(wf, "EXISTING_PRODUCT_BASELINE.md", [
        "Product identity",
        "Route and surface inventory",
        "Current visual baseline",
        "Existing constraints",
        "Baseline evidence",
    ], min_rows=1))
    findings.extend(check_text_artifact(wf, "API_BACKEND_FEASIBILITY_MAP.md", [
        "Visible user function",
        "Existing backend/API/data support",
        "Required adaptation / contract-needed",
        "Prototype UI treatment",
        "Backend impact summary",
    ], min_rows=1))
    findings.extend(check_text_artifact(wf, "PRODUCT_SURFACE_LANGUAGE_RULES.md", [
        "Forbidden user-visible terms",
        "Translation rules",
        "Requirement",
    ], min_rows=3, min_cols=2))
    min_trace_rows = 3 if risk.upper() == "C" else 5
    findings.extend(check_text_artifact(wf, "PROTOTYPE_REQUIREMENT_TRACE.md", [
        "Requirement / source anchor",
        "Backend/API feasibility",
        "Non-regression rule",
        "Preserved existing surfaces",
    ], min_rows=min_trace_rows))
    return {"status": "PASS" if not findings else "FAIL", "workflow": str(wf), "risk": risk.upper(), "findings": findings}


def check_prototype(workflow: Path, prototype_raw: str) -> dict[str, Any]:
    try:
        proto = Path(prototype_raw)
        if not proto.is_absolute():
            proto = workflow / proto
        proto = proto.resolve()
        if not is_within(proto, workflow):
            raise ValueError("prototype must stay under workflow")
    except Exception as exc:
        return {"status": "FAIL", "prototype": prototype_raw, "findings": [finding("error", prototype_raw, str(exc))]}
    if not nonempty(proto, 120):
        return {"status": "FAIL", "prototype": str(proto), "findings": [finding("error", proto, "prototype missing or too thin")]}
    visible = visible_text(read(proto))
    banned = [term for term in BANNED_VISIBLE_TERMS if banned_term_present(term, visible)]
    findings = [finding("error", proto, "prototype visible UI contains internal governance language: " + ", ".join(sorted(set(banned))))] if banned else []
    return {"status": "PASS" if not findings else "FAIL", "prototype": str(proto), "banned_terms": sorted(set(banned)), "findings": findings}


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate existing-product intake before AI high-fidelity prototype generation.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--workflow")
    ap.add_argument("--risk", choices=["C", "D"], default="C")
    ap.add_argument("--prototype", help="Optional prototype HTML to scan for user-visible internal language")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    base_findings = check_templates(root)
    result: dict[str, Any] = {"status": "PASS" if not base_findings else "FAIL", "base": {"findings": base_findings}}
    if args.workflow:
        wf_result = check_workflow(root, args.workflow, args.risk)
        proto_result = None
        if args.prototype and wf_result["status"] in {"PASS", "FAIL"}:
            wf_path = Path(wf_result.get("workflow", args.workflow)).resolve()
            proto_result = check_prototype(wf_path, args.prototype)
        findings = base_findings + wf_result.get("findings", []) + ((proto_result or {}).get("findings", []))
        result = {"status": "PASS" if not findings else "FAIL", "base": {"findings": base_findings}, "workflow": wf_result, "prototype": proto_result, "findings": findings}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("status=" + result["status"])
        for f in result.get("findings", base_findings):
            print(f"{f['severity']}: {f['path']}: {f['message']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
