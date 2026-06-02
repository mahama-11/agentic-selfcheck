#!/usr/bin/env python3
from __future__ import annotations
import argparse
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "prototype_dual_model_gate.py"

HTML_BASE = """<!doctype html><html><head><style>.visual{{}}</style></head><body>{body}<script>console.log('ok')</script></body></html>"""

def write_case(wf: Path, *, kimi_origin: str) -> None:
    (wf / "raw").mkdir()
    (wf / "imgs").mkdir()
    (wf / "imgs/image_007.png").write_bytes(b"x" * 500)
    (wf / "raw/current.html").write_text("current raw" * 50)
    (wf / "raw/kimi.html").write_text("kimi raw direct image" * 50)
    current_body = "\n".join(f"<div class='visual candidate card'>Current 图片窗口 {i}</div>" for i in range(80))
    kimi_body = "\n".join(f"<section><div class='image-window candidate card'>Kimi 候选图片区 {i}</div><button>选择{i}</button></section>" for i in range(90))
    (wf / "current.html").write_text(HTML_BASE.format(body=current_body))
    (wf / "kimi.html").write_text(HTML_BASE.format(body=kimi_body + "<p>" + "差异" * 120 + "</p>"))
    (wf / "current-delta.md").write_text("model_lane: current\nready_for_user_review: true\nvisual_review: PASS\nnotes: independent current lane with enough review evidence for smoke fixture\n")
    (wf / "kimi-delta.md").write_text("model_lane: kimi\nready_for_user_review: true\nvisual_review: PASS\nnotes: independent kimi lane with enough review evidence for smoke fixture\n")
    (wf / "comparison.md").write_text("Current and Kimi comparison\ntakeaway: different\nrisk: low\nnotes: smoke fixture comparison contains required tokens and adequate length for gate fixture validation.\n")
    (wf / "current-origin.md").write_text("model_lane: current\ngeneration_origin: raw_model_output\nraw_output: raw/current.html\nnotes: independent current model evidence with adequate raw output pointer and enough fixture length for gate validation.\n")
    (wf / "kimi-origin.md").write_text(kimi_origin)


def run_gate(wf: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([
        str(GATE), "--workflow", str(wf),
        "--current-prototype", "current.html",
        "--kimi-prototype", "kimi.html",
        "--current-delta", "current-delta.md",
        "--kimi-delta", "kimi-delta.md",
        "--comparison", "comparison.md",
        "--current-origin", "current-origin.md",
        "--kimi-origin", "kimi-origin.md",
        "--format", "text",
    ], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--format", choices=["text"], default="text")
    ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        bad = base / "bad"; bad.mkdir()
        write_case(bad, kimi_origin="model_lane: kimi\ngeneration_origin: raw_model_output\nraw_output: raw/kimi.html\nvisual_context: text summary only, path only\n")
        bad_res = run_gate(bad)
        assert bad_res.returncode != 0, bad_res.stdout
        assert "direct visual input" in bad_res.stdout or "text-only/path-only" in bad_res.stdout, bad_res.stdout

        good = base / "good"; good.mkdir()
        write_case(good, kimi_origin="model_lane: kimi\ngeneration_origin: raw_model_output\nraw_output: raw/kimi.html\nimage_inputs:\n  - imgs/image_007.png\nvisual_input_evidence: opencode --file image attachment; direct image block; multimodal vision input confirmed\n")
        good_res = run_gate(good)
        assert good_res.returncode == 0, good_res.stdout
    print("PASS prototype_dual_model_vision_smoke")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
