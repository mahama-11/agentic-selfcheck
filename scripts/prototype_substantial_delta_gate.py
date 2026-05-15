#!/usr/bin/env python3
from __future__ import annotations
import argparse, difflib, json, re
from pathlib import Path


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def visible_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def finding(path: Path, msg: str) -> dict:
    return {"severity": "error", "path": str(path), "message": msg}


def main() -> int:
    ap = argparse.ArgumentParser(description="Prevent cosmetic patches from being presented as a new prototype iteration.")
    ap.add_argument("--previous", required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--mode", choices=["new-iteration", "hardening-pass"], default="new-iteration")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    prev = Path(args.previous).resolve()
    cand = Path(args.candidate).resolve()
    findings = []
    if not prev.exists():
        findings.append(finding(prev, "previous prototype missing"))
        prev_html = ""
    else:
        prev_html = read(prev)
    if not cand.exists():
        findings.append(finding(cand, "candidate prototype missing"))
        cand_html = ""
    else:
        cand_html = read(cand)

    prev_lines = prev_html.splitlines()
    cand_lines = cand_html.splitlines()
    line_ratio = difflib.SequenceMatcher(None, prev_lines, cand_lines).ratio() if prev_lines or cand_lines else 0
    prev_text = visible_text(prev_html)
    cand_text = visible_text(cand_html)
    text_ratio = difflib.SequenceMatcher(None, prev_text, cand_text).ratio() if prev_text or cand_text else 0
    changed_lines = sum(1 for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, prev_lines, cand_lines).get_opcodes() if tag != "equal" for _ in range(max(i2 - i1, j2 - j1)))
    new_visible_chars = max(0, len(cand_text) - len(prev_text))
    metrics = {
        "line_similarity": round(line_ratio, 4),
        "visible_text_similarity": round(text_ratio, 4),
        "changed_lines": changed_lines,
        "new_visible_chars": new_visible_chars,
        "mode": args.mode,
    }

    if args.mode == "new-iteration":
        if line_ratio > 0.94:
            findings.append(finding(cand, f"candidate too similar to previous for a new iteration: line_similarity={line_ratio:.4f} > 0.94"))
        if changed_lines < 80:
            findings.append(finding(cand, f"candidate changes too small for a new iteration: changed_lines={changed_lines} < 80"))
        if text_ratio > 0.96:
            findings.append(finding(cand, f"visible content too similar for a new iteration: visible_text_similarity={text_ratio:.4f} > 0.96"))

    result = {"status": "PASS" if not findings else "FAIL", "metrics": metrics, "findings": findings}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status={result['status']} mode={args.mode} line_similarity={metrics['line_similarity']} visible_text_similarity={metrics['visible_text_similarity']} changed_lines={changed_lines} findings={len(findings)}")
        for f in findings:
            print(f"ERROR: {f['path']}: {f['message']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
