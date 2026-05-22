#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from prototype_path_utils import resolve_under


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
    governed = (root / ".hermes/workflows").resolve()
    resolved = wf.resolve()
    try:
        resolved.relative_to(governed)
    except Exception as exc:
        raise ValueError("workflow must stay under governed .hermes/workflows") from exc
    if path_has_symlink(wf, governed):
        raise ValueError("workflow path components must not be symlinked")
    return resolved

FOUNDATION_REQUIRED = [
    "DOCUMENT_REQUIREMENT_COVERAGE.md",
    "PROJECT_CONTEXT.md",
    "PRODUCT_PROTOTYPE_BACKBONE.md",
    "PRODUCT_PROTOTYPE_VISUAL_BACKBONE.md",
    "24-existing-project-style-baseline.md",
    "26-prototype-foundation-and-non-regression-protocol.md",
]

DELTA_REQUIRED_FIELDS = [
    "prototype_id",
    "model_lane",
    "base_version",
    "preserved",
    "added",
    "removed",
    "weakened",
    "project_style_alignment",
    "ready_for_user_review",
]

BANNED_VISIBLE_TERMS = [
    "V1", "V2", "V3", "Stage", "contract-needed", "backend gap", "API gap",
    "gate", "verifier", "coverage", "GPU", "TFlops", "Stable Diffusion",
    "AI 推理引擎在线", "Test001", "Test002", "Test003",
]

REQUIRED_BUSINESS_TERMS = [
    "商品", "SKU", "参考", "解构", "意图", "映射", "生成", "微调", "保存",
]

PROJECT_STYLE_TERMS = [
    "#0a0a12", "#0b0d14", "#3b82f6", "#8b5cf6", "Product", "Visual", "Workbench",
]

REQUIRED_PAGE_TERMS = [
    "画面解构", "意图映射", "Prompt", "候选微调", "保存同步",
]


def finding(severity: str, path: str, message: str) -> dict:
    return {"severity": severity, "path": path, "message": message}


def nonempty(path: Path, min_bytes: int = 40) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size >= min_bytes


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def strip_html(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_simple_delta(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    current_key: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#") or line.strip() in {"```yaml", "```"}:
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if m:
            current_key = m.group(1)
            data[current_key] = m.group(2).strip()
            continue
        if current_key and re.match(r"^\s*-\s+", line):
            item = re.sub(r"^\s*-\s+", "", line).strip()
            data[current_key] = (data.get(current_key, "") + "\n" + item).strip()
    return data


def has_meaningful_value(value: str | None) -> bool:
    if value is None:
        return False
    v = value.strip().strip("[]")
    return bool(v) and v.lower() not in {"todo", "tbd", "none", "n/a", "na", "-", "[]"}


def check_foundation(workflow: Path) -> list[dict]:
    findings: list[dict] = []
    for rel in FOUNDATION_REQUIRED:
        path = workflow / rel
        if not nonempty(path):
            findings.append(finding("error", str(path), "required foundation artifact missing or empty"))
    return findings


def check_delta(delta_path: Path) -> tuple[list[dict], dict[str, str]]:
    findings: list[dict] = []
    if not nonempty(delta_path):
        return [finding("error", str(delta_path), "prototype iteration delta missing or empty")], {}
    data = parse_simple_delta(read_text(delta_path))
    for field in DELTA_REQUIRED_FIELDS:
        if field in {"removed", "weakened"}:
            if field not in data:
                findings.append(finding("error", str(delta_path), f"required delta field missing: {field}"))
            continue
        if not has_meaningful_value(data.get(field)):
            findings.append(finding("error", str(delta_path), f"required delta field missing or placeholder: {field}"))
    removed = data.get("removed", "")
    weakened = data.get("weakened", "")
    accepted = data.get("accepted_tradeoff", "") or data.get("human_accepted_tradeoff", "")
    if (has_meaningful_value(removed) or has_meaningful_value(weakened)) and not has_meaningful_value(accepted):
        findings.append(finding("error", str(delta_path), "removed/weakened foundation requires explicit accepted_tradeoff"))
    psa = (data.get("project_style_alignment", "") or "").lower()
    if "fail" in psa:
        findings.append(finding("error", str(delta_path), "project_style_alignment is fail"))
    ready = (data.get("ready_for_user_review", "") or "").lower()
    if ready not in {"true", "yes", "pass"}:
        findings.append(finding("error", str(delta_path), "ready_for_user_review must be true/yes/pass before presentation"))
    return findings, data


def check_prototype(proto_path: Path, min_bytes: int, min_controls: int, min_visible_chars: int, min_pages: int, min_interaction_markers: int) -> tuple[list[dict], dict]:
    findings: list[dict] = []
    if not nonempty(proto_path, min_bytes=200):
        return [finding("error", str(proto_path), "prototype missing or too small")], {}
    text = read_text(proto_path)
    visible = strip_html(text)
    buttons = len(re.findall(r"<button\b|role=[\"']button[\"']|<a\b", text, flags=re.I))
    sections = len(re.findall(r"<section\b|data-surface=|class=[\"'][^\"']*(?:surface|panel|step|workspace)", text, flags=re.I))
    pages = len(set(re.findall(r"data-page=[\"']([^\"']+)[\"']", text, flags=re.I)))
    if pages == 0:
        pages = len(re.findall(r"class=[\"'][^\"']*(?:page|screen)[^\"']*[\"']", text, flags=re.I))
    nav_targets = len(re.findall(r"data-target=|data-nav=|href=[\"']#", text, flags=re.I))
    interaction_markers = len(re.findall(r"addEventListener|onclick=|querySelector|classList\.|data-target=|data-select=|toast|drawer|modal|active|selected|hover", text, flags=re.I))
    missing_terms = [term for term in REQUIRED_BUSINESS_TERMS if term not in visible]
    missing_pages = [term for term in REQUIRED_PAGE_TERMS if term not in visible]
    banned = [term for term in BANNED_VISIBLE_TERMS if term.lower() in visible.lower()]
    style_hits = [term for term in PROJECT_STYLE_TERMS if term in text or term in visible]
    if len(text.encode("utf-8")) < min_bytes:
        findings.append(finding("error", str(proto_path), f"prototype below min bytes: {len(text.encode('utf-8'))} < {min_bytes}"))
    if buttons < min_controls:
        findings.append(finding("error", str(proto_path), f"interactive controls below minimum: {buttons} < {min_controls}"))
    if len(visible) < min_visible_chars:
        findings.append(finding("error", str(proto_path), f"visible text below minimum: {len(visible)} < {min_visible_chars}"))
    if pages < min_pages:
        findings.append(finding("error", str(proto_path), f"reviewable pages/modules below minimum: {pages} < {min_pages}"))
    if nav_targets < min_pages:
        findings.append(finding("error", str(proto_path), f"page navigation targets below minimum: {nav_targets} < {min_pages}"))
    if interaction_markers < min_interaction_markers:
        findings.append(finding("error", str(proto_path), f"interaction markers below minimum: {interaction_markers} < {min_interaction_markers}"))
    if missing_terms:
        findings.append(finding("error", str(proto_path), "missing required business concepts: " + ", ".join(missing_terms)))
    if missing_pages:
        findings.append(finding("error", str(proto_path), "missing required V2 page/module concepts: " + ", ".join(missing_pages)))
    if banned:
        findings.append(finding("error", str(proto_path), "visible UI contains banned internal terms: " + ", ".join(sorted(set(banned)))))
    if len(style_hits) < 3:
        findings.append(finding("error", str(proto_path), "project style alignment too weak; expected Ecommerce shell/token markers"))
    metrics = {
        "bytes": len(text.encode("utf-8")),
        "sections_or_surfaces": sections,
        "pages_or_modules": pages,
        "navigation_targets": nav_targets,
        "interaction_markers": interaction_markers,
        "buttons_or_links": buttons,
        "visible_chars": len(visible),
        "missing_business_terms": missing_terms,
        "missing_page_terms": missing_pages,
        "banned_terms": sorted(set(banned)),
        "project_style_hits": style_hits,
    }
    return findings, metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed foundation/non-regression gate for existing-product high-fidelity prototypes.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--workflow", required=True, help="Workflow directory containing foundation artifacts")
    parser.add_argument("--prototype", help="Candidate prototype HTML path, relative to workflow or absolute")
    parser.add_argument("--delta", help="Iteration delta file path, relative to workflow or absolute")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--min-bytes", type=int, default=20000)
    parser.add_argument("--min-controls", type=int, default=10)
    parser.add_argument("--min-visible-chars", type=int, default=2500)
    parser.add_argument("--min-pages", type=int, default=4)
    parser.add_argument("--min-interaction-markers", type=int, default=8)
    args = parser.parse_args()

    workflow_valid = True
    try:
        workflow = resolve_workflow(Path(args.root).resolve(), args.workflow)
        findings = check_foundation(workflow)
    except ValueError as exc:
        workflow = Path(args.workflow).resolve()
        findings = [finding("error", str(workflow), str(exc))]
        workflow_valid = False
    metrics: dict = {}
    delta_data: dict = {}

    if workflow_valid and args.delta:
        try:
            delta_path = resolve_under(workflow, args.delta, "delta")
            delta_findings, delta_data = check_delta(delta_path)
        except ValueError as exc:
            delta_findings, delta_data = [finding("error", str(workflow), str(exc))], {}
        findings.extend(delta_findings)
    if workflow_valid and args.prototype:
        try:
            proto_path = resolve_under(workflow, args.prototype, "prototype")
            proto_findings, metrics = check_prototype(proto_path, args.min_bytes, args.min_controls, args.min_visible_chars, args.min_pages, args.min_interaction_markers)
        except ValueError as exc:
            proto_findings, metrics = [finding("error", str(workflow), str(exc))], {}
        findings.extend(proto_findings)

    result = {
        "status": "PASS" if not any(f["severity"] == "error" for f in findings) else "FAIL",
        "workflow": str(workflow),
        "prototype_metrics": metrics,
        "delta": delta_data,
        "findings": findings,
    }
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']} findings={len(findings)}")
        for f in findings:
            print(f"{f['severity'].upper()}: {f['path']}: {f['message']}")
        if metrics:
            print("metrics=" + json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
