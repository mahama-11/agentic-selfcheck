#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from prototype_path_utils import resolve_under

REQUIRED_TERMS = [
    ("primary_anchors", ["primary anchor", "primary anchors", "核心锚点", "关键图", "主锚点"]),
    ("secondary_references", ["secondary", "background", "一轮", "背景参考", "次要参考", "secondary reference"]),
    ("page_mapping", ["page mapping", "页面映射", "页面职责", "module responsibility", "page responsibility"]),
    ("not_merged", ["not merge", "不要揉", "不揉", "separate page", "独立页面", "不合并"]),
]
BAD_PHRASES = [
    "all images equal",
    "treat all images equally",
    "single long page",
    "one long page",
    "merged dashboard",
    "全部等权",
    "揉成一个页面",
    "揉成一页",
    "一个长页",
]
LOW_FI_MARKERS = ["placeholder", "占位", "wireframe", "低保真", "示意"]


def finding(status: str, message: str) -> dict:
    return {"status": status, "message": message}


def contains_any(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(term.lower() in low for term in terms)


def extract_expected_pages(text: str) -> list[str]:
    pages: list[str] = []
    # Prefer explicit markdown bullets like: - page: xxx / 页面: xxx
    for m in re.finditer(r"(?:page|页面|模块)\s*[:：]\s*([^\n#|]+)", text, re.I):
        val = m.group(1).strip(" -*`：:；;，,。")
        if val and len(val) <= 80:
            pages.append(val)
    # Also accept table rows containing explicit page/module responsibility.
    for line in text.splitlines():
        if "|" in line and any(k in line for k in ["页面", "page", "Page", "模块"]):
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if parts and not any(sep in parts[0] for sep in ["---", "Page", "页面"]):
                pages.append(parts[0])
    # de-dupe preserving order
    out = []
    for p in pages:
        if p not in out:
            out.append(p)
    return out


def count_html_pages(html: str) -> int:
    # Count explicit prototype pages, nav tabs, route pages, or full-page sections.
    patterns = [
        r'<section\b[^>]*class=["\'][^"\']*\bpage\b',
        r'data-page=["\']',
        r'role=["\']tabpanel["\']',
        r'<a\b[^>]*href=["\']#[^"\']+["\'][^>]*>[^<]{2,}',
    ]
    counts = [len(re.findall(p, html, re.I)) for p in patterns]
    return max(counts) if counts else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Fail-closed page semantics gate for DOCX/screenshot-driven prototypes.")
    ap.add_argument("--semantics", required=True, help="PAGE_SEMANTICS.md / requirement decomposition file")
    ap.add_argument("--prototype", help="Candidate HTML prototype")
    ap.add_argument("--workflow", help="Optional workflow root; when set, semantics/prototype must be relative and contained")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    findings: list[dict] = []
    if args.workflow:
        workflow = Path(args.workflow).resolve()
        try:
            semantics = resolve_under(workflow, args.semantics, "semantics")
        except ValueError as exc:
            semantics = workflow / "<invalid-semantics-path>"
            findings.append(finding("FAIL", str(exc)))
    else:
        semantics = Path(args.semantics).resolve()
    if not semantics.exists() or semantics.stat().st_size < 300:
        findings.append(finding("FAIL", "missing or too small page semantics file"))
        text = ""
    else:
        text = semantics.read_text(errors="replace")

    for key, terms in REQUIRED_TERMS:
        if not contains_any(text, terms):
            findings.append(finding("FAIL", f"page semantics missing required concept: {key}"))

    low = text.lower()
    for phrase in BAD_PHRASES:
        start = 0
        while True:
            idx = low.find(phrase.lower(), start)
            if idx < 0:
                break
            window = low[max(0, idx - 96):idx]
            # Allow explicit prohibitions such as "do not merge into one long page" in the constraint file.
            if not any(neg in window for neg in ["not ", "do not", "don't", "never", "不要", "不"]):
                findings.append(finding("FAIL", f"page semantics contains forbidden anti-pattern phrase: {phrase}"))
            start = idx + len(phrase)

    pages = extract_expected_pages(text)
    if len(pages) < 2:
        findings.append(finding("FAIL", "expected at least 2 explicit page/module responsibilities for multi-screenshot serious prototype"))

    if args.prototype:
        if args.workflow:
            try:
                proto = resolve_under(Path(args.workflow).resolve(), args.prototype, "prototype")
            except ValueError as exc:
                proto = Path(args.workflow).resolve() / "<invalid-prototype-path>"
                findings.append(finding("FAIL", str(exc)))
        else:
            proto = Path(args.prototype).resolve()
        if not proto.exists() or proto.stat().st_size < 1000:
            findings.append(finding("FAIL", "missing or too small prototype HTML"))
            html = ""
        else:
            html = proto.read_text(errors="replace")
        html_pages = count_html_pages(html)
        if pages and html_pages and html_pages < min(len(pages), 3):
            findings.append(finding("FAIL", f"prototype page count appears too low: html_pages={html_pages}, semantic_pages={len(pages)}"))
        if any(marker in html.lower() for marker in LOW_FI_MARKERS):
            findings.append(finding("FAIL", "prototype contains low-fidelity/placeholder markers; do not present as high-fidelity"))

    status = "FAIL" if any(f["status"] == "FAIL" for f in findings) else "PASS"
    payload = {"status": status, "semantics": str(semantics), "pages": pages, "findings": findings}
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"status={status} pages={len(pages)}")
        for f in findings:
            print(f"[{f['status']}] {f['message']}")
    return 0 if status == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
