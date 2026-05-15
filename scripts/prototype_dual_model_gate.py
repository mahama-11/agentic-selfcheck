#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from difflib import SequenceMatcher
from pathlib import Path
from prototype_path_utils import resolve_under


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def parse_kv(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    current = None
    for raw in read(path).splitlines():
        line = raw.rstrip()
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            current = m.group(1)
            data[current] = m.group(2).strip()
        elif current and re.match(r"^\s*-\s+", line):
            data[current] = (data.get(current, "") + "\n" + re.sub(r"^\s*-\s+", "", line).strip()).strip()
    return data


def finding(path: Path, message: str) -> dict:
    return {"severity": "error", "path": str(path), "message": message}


def similarity_metrics(a: str, b: str) -> dict[str, float | int]:
    a_lines = a.splitlines()
    b_lines = b.splitlines()
    paired_changes = sum(1 for x, y in zip(a_lines, b_lines) if x != y)
    changed_lines = paired_changes + abs(len(a_lines) - len(b_lines))
    return {
        "line_similarity": round(SequenceMatcher(None, a_lines, b_lines).ratio(), 4),
        "text_similarity": round(SequenceMatcher(None, a, b).ratio(), 4),
        "changed_lines": changed_lines,
        "current_lines": len(a_lines),
        "kimi_lines": len(b_lines),
    }


def _resolve_workflow_path(evidence_path: Path, ref: str) -> Path:
    return resolve_under(evidence_path.parent, ref, "referenced evidence path")


def _check_ref_inside_workflow(evidence_path: Path, ref_path: Path, label: str) -> list[dict]:
    try:
        ref_path.relative_to(evidence_path.parent.resolve())
    except ValueError:
        return [finding(evidence_path, f"{label} path must stay inside workflow directory")]
    return []


def evidence_ok(path: Path, expected_model: str) -> list[dict]:
    findings: list[dict] = []
    if not path.exists() or path.stat().st_size < 120:
        return [finding(path, f"missing or too small model-origin evidence for {expected_model}")]
    data = parse_kv(path)
    text = read(path)
    text_lower = text.lower()
    model = (data.get("model_lane") or data.get("model") or "").lower()
    origin = (data.get("generation_origin") or data.get("origin") or "").lower()
    raw_ref = data.get("raw_output") or data.get("raw_output_path") or data.get("transcript") or ""
    if expected_model not in model:
        findings.append(finding(path, f"origin evidence must declare model_lane/model containing {expected_model}"))
    if not any(token in origin for token in ["raw_model_output", "model_direct", "independent_model"]):
        findings.append(finding(path, "origin evidence must declare generation_origin: raw_model_output/model_direct/independent_model"))
    if any(token in text_lower for token in ["local assembly", "local implementation", "synthesized", "hand-edited", "hand edited", "orchestrator assembled"]):
        findings.append(finding(path, "origin evidence says this is synthesized/local assembly; cannot count as independent model lane"))
    if expected_model == "kimi":
        vision_tokens = [
            "image block",
            "image attachment",
            "direct image",
            "vision input",
            "multimodal",
            "--file",
            "type: image",
            "type=image",
            "image_inputs",
            "image_attachments",
        ]
        negative_tokens = [
            "text summary only",
            "text-only summary",
            "文字转述 only",
            "no image attachment",
            "path only",
        ]
        image_refs = data.get("image_inputs") or data.get("image_attachments") or data.get("vision_inputs") or ""
        if not any(token in text_lower for token in vision_tokens):
            findings.append(finding(path, "kimi origin must prove direct visual input: image block / image attachment / opencode --file evidence"))
        if any(token in text_lower for token in negative_tokens):
            findings.append(finding(path, "kimi origin evidence admits text-only/path-only visual context; cannot satisfy visual lane"))
        if not re.search(r"\.(png|jpe?g|webp)\b", image_refs, flags=re.I):
            findings.append(finding(path, "kimi origin must list image_inputs/image_attachments with concrete image files"))
        else:
            for ref in [x.strip() for x in re.split(r"[\n,]", image_refs) if x.strip()]:
                if not re.search(r"\.(png|jpe?g|webp)\b", ref, flags=re.I):
                    continue
                ref_path = _resolve_workflow_path(path, ref)
                findings.extend(_check_ref_inside_workflow(path, ref_path, "image input"))
                if not ref_path.exists() or ref_path.stat().st_size < 200:
                    findings.append(finding(ref_path, "referenced Kimi image input missing or too small"))
    if raw_ref:
        raw_path = _resolve_workflow_path(path, raw_ref)
        findings.extend(_check_ref_inside_workflow(path, raw_path, "raw_output"))
        if not raw_path.exists() or raw_path.stat().st_size < 200:
            findings.append(finding(raw_path, "referenced raw model output missing or too small"))
    else:
        # allow inline raw snippets, but require enough content to be audit useful
        if len(text) < 800:
            findings.append(finding(path, "origin evidence needs raw_output/raw_output_path/transcript or substantial inline raw output"))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="Require synchronized, independent Current + Kimi prototype lanes.")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--current-prototype", required=True)
    ap.add_argument("--kimi-prototype", required=True)
    ap.add_argument("--current-delta", required=True)
    ap.add_argument("--kimi-delta", required=True)
    ap.add_argument("--comparison", required=True)
    ap.add_argument("--current-origin", required=True, help="Evidence file proving independent Current model generation")
    ap.add_argument("--kimi-origin", required=True, help="Evidence file proving independent Kimi model generation")
    ap.add_argument("--max-line-similarity", type=float, default=0.92)
    ap.add_argument("--max-text-similarity", type=float, default=0.97)
    ap.add_argument("--min-changed-lines", type=int, default=40)
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args()

    wf = Path(args.workflow).resolve()
    findings: list[dict] = []
    files = {}
    for name, value in {
        "current_prototype": args.current_prototype,
        "kimi_prototype": args.kimi_prototype,
        "current_delta": args.current_delta,
        "kimi_delta": args.kimi_delta,
        "comparison": args.comparison,
        "current_origin": args.current_origin,
        "kimi_origin": args.kimi_origin,
    }.items():
        try:
            files[name] = resolve_under(wf, value, name)
        except ValueError as exc:
            invalid = wf / f"<invalid-{name}-path>"
            files[name] = invalid
            findings.append(finding(wf, str(exc)))
    for name, path in files.items():
        if not path.exists() or path.stat().st_size < 80:
            findings.append(finding(path, f"required dual-model artifact missing or too small: {name}"))

    metrics = {}
    if not findings:
        current_delta = parse_kv(files["current_delta"])
        kimi_delta = parse_kv(files["kimi_delta"])
        if current_delta.get("model_lane", "").strip().lower() != "current":
            findings.append(finding(files["current_delta"], "current delta must declare model_lane: current"))
        if kimi_delta.get("model_lane", "").strip().lower() != "kimi":
            findings.append(finding(files["kimi_delta"], "kimi delta must declare model_lane: kimi"))
        for lane_name, delta_path, delta in [
            ("current", files["current_delta"], current_delta),
            ("kimi", files["kimi_delta"], kimi_delta),
        ]:
            ready = delta.get("ready_for_user_review", "").strip().lower()
            visual_review = delta.get("visual_review", "").strip().lower()
            if ready not in ["true", "yes", "pass"]:
                findings.append(finding(delta_path, f"{lane_name} delta is not ready_for_user_review: {ready or 'missing'}"))
            if visual_review and not visual_review.startswith("pass"):
                findings.append(finding(delta_path, f"{lane_name} visual_review is not PASS: {visual_review}"))

        findings.extend(evidence_ok(files["current_origin"], "current"))
        findings.extend(evidence_ok(files["kimi_origin"], "kimi"))

        comparison = read(files["comparison"])
        for token in ["Current", "Kimi", "takeaway", "risk"]:
            if token not in comparison:
                findings.append(finding(files["comparison"], f"comparison missing token: {token}"))

        current_html = read(files["current_prototype"])
        kimi_html = read(files["kimi_prototype"])
        for label, path, html in [
            ("current", files["current_prototype"], current_html),
            ("kimi", files["kimi_prototype"], kimi_html),
        ]:
            lower = html.lower()
            for token in ["<html", "<style", "<script", "</body>", "</html>"]:
                if token not in lower:
                    findings.append(finding(path, f"{label} prototype incomplete: missing {token}"))
            image_window_count = len(re.findall(r"image-window|visual|candidate|候选|图片窗口|gallery|thumb", html, flags=re.I))
            if image_window_count < 6:
                findings.append(finding(path, f"{label} prototype lacks enough image/window/candidate surfaces: {image_window_count} < 6"))
        metrics = similarity_metrics(current_html, kimi_html)
        if metrics["line_similarity"] > args.max_line_similarity:
            findings.append(finding(files["comparison"], f"model lanes too structurally similar: line_similarity={metrics['line_similarity']} > {args.max_line_similarity}"))
        if metrics["text_similarity"] > args.max_text_similarity:
            findings.append(finding(files["comparison"], f"model lanes too text-similar: text_similarity={metrics['text_similarity']} > {args.max_text_similarity}"))
        if metrics["changed_lines"] < args.min_changed_lines:
            findings.append(finding(files["comparison"], f"model lanes changed lines too small: {metrics['changed_lines']} < {args.min_changed_lines}"))

    result = {"status": "PASS" if not findings else "FAIL", "metrics": metrics, "findings": findings}
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        metric_text = " ".join(f"{k}={v}" for k, v in metrics.items())
        print(f"status={result['status']} findings={len(findings)} {metric_text}".rstrip())
        for f in findings:
            print(f"ERROR: {f['path']}: {f['message']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
