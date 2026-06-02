#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from prototype_path_utils import resolve_under


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def finding(path: Path, message: str) -> dict:
    return {"severity": "error", "path": str(path), "message": message}


def count(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.I | re.S))


def main() -> int:
    ap = argparse.ArgumentParser(description="Require prototype interaction affordances learned from the stronger Kimi lane.")
    ap.add_argument("--prototype", required=True, help="Prototype HTML file")
    ap.add_argument("--workflow", help="Optional workflow root; when set, prototype must be relative and contained")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()
    findings: list[dict] = []
    if args.workflow:
        try:
            path = resolve_under(Path(args.workflow).resolve(), args.prototype, "prototype")
        except ValueError as exc:
            path = Path(args.workflow).resolve() / "<invalid-prototype-path>"
            findings.append(finding(Path(args.workflow).resolve(), str(exc)))
    else:
        path = Path(args.prototype).resolve()
    if not path.exists():
        findings.append(finding(path, "prototype file missing"))
        text = ""
    else:
        text = read(path)

    metrics = {
        "hover_rules": count(r":hover", text),
        "tooltips": count(r"data-tip|tooltip|\[data-tip\]", text),
        "progress_markers": count(r"progress|progress-fill|progress-bar", text),
        "colored_labels": count(r"status-label|\btag\b|label", text),
        "transitions": count(r"transition\s*:", text),
        "animations": count(r"@keyframes|animation\s*:", text),
        "selected_states": count(r"selected", text),
    }
    thresholds = {
        "hover_rules": 5,
        "tooltips": 2,
        "progress_markers": 3,
        "colored_labels": 6,
        "transitions": 4,
        "animations": 1,
        "selected_states": 8,
    }
    for key, minimum in thresholds.items():
        if metrics[key] < minimum:
            findings.append(finding(path, f"interaction affordance too weak: {key}={metrics[key]} < {minimum}"))

    # Avoid fake CSS-only tokens: require at least one JS state update for progress/status/toast.
    if text and not re.search(r"progressMap|routeProgress|style\.width|showToast", text, flags=re.I):
        findings.append(finding(path, "missing runtime state feedback for progress/toast/status"))

    result = {"status": "PASS" if not findings else "FAIL", "metrics": metrics, "findings": findings}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("status={status} hover_rules={hover_rules} tooltips={tooltips} progress_markers={progress_markers} colored_labels={colored_labels} transitions={transitions} animations={animations} selected_states={selected_states} findings={findings}".format(
            status=result["status"], findings=len(findings), **metrics
        ))
        for f in findings:
            print(f"ERROR: {f['path']}: {f['message']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
