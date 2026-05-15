#!/usr/bin/env python3
from __future__ import annotations
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().with_name("prototype_foundation_gate.py")

FOUNDATION_FILES = {
    "DOCUMENT_REQUIREMENT_COVERAGE.md": "coverage ok\n" * 8,
    "PROJECT_CONTEXT.md": "project context ok\n" * 8,
    "PRODUCT_PROTOTYPE_BACKBONE.md": "商品 SKU 参考 解构 意图 映射 生成 微调 保存\n" * 8,
    "PRODUCT_PROTOTYPE_VISUAL_BACKBONE.md": "visual backbone ok\n" * 8,
    "24-existing-project-style-baseline.md": "#0a0a12 #0b0d14 #3b82f6 #8b5cf6 Product Visual Workbench\n" * 8,
    "26-prototype-foundation-and-non-regression-protocol.md": "non regression ok\n" * 8,
}

GOOD_DELTA = """
prototype_id: good
model_lane: current
base_version: v5-rejected
preserved:
  - requirement origin
  - project style baseline
added:
  - project aligned shell
removed: none
weakened: none
project_style_alignment: pass
ready_for_user_review: true
"""

BAD_DELTA = """
prototype_id: bad
model_lane: current
base_version: v5-rejected
preserved:
  - some
added:
  - new style
removed:
  - project shell
weakened: none
project_style_alignment: fail
ready_for_user_review: true
"""

GOOD_HTML = """
<!doctype html><html><head><style>
body{background:#0a0a12;color:white}.shell{background:#0b0d14;border:1px solid rgba(255,255,255,.06)}.brand{color:#3b82f6}.accent{color:#8b5cf6}
</style></head><body>
<div class="shell Product Visual Workbench">
<section data-page="product" data-surface="product">商品 SKU 参考 画面解构 意图映射 Prompt 候选微调 保存同步 商品 SKU 参考 解构 意图 映射 生成 微调 保存</section>
<section data-page="reference" data-surface="reference">商品 SKU 参考 画面解构 意图映射 Prompt 候选微调 保存同步</section>
<section data-page="deconstruct" data-surface="deconstruct">商品 SKU 参考 画面解构 意图映射 Prompt 候选微调 保存同步</section>
<section data-page="intent" data-surface="intent">商品 SKU 参考 画面解构 意图映射 Prompt 候选微调 保存同步</section>
<section data-page="generation" data-surface="generation">商品 SKU 参考 画面解构 意图映射 Prompt 候选微调 保存同步</section>
<section data-page="refine" data-surface="refine">商品 SKU 参考 画面解构 意图映射 Prompt 候选微调 保存同步</section>
<section data-page="save" data-surface="save">商品 SKU 参考 画面解构 意图映射 Prompt 候选微调 保存同步</section>
<nav><a href="#product" data-target="product">商品</a><a href="#reference" data-target="reference">参考</a><a href="#deconstruct" data-target="deconstruct">解构</a><a href="#intent" data-target="intent">意图</a></nav>
<script>document.querySelectorAll('button,a').forEach(el=>el.addEventListener('click',()=>{document.body.classList.toggle('active'); const toast=document.createElement('div'); toast.className='toast selected'; toast.dataset.select='1'; document.body.appendChild(toast)}));</script>
<button>确认商品</button><button>添加参考</button><button>开始解构</button><button>确认意图</button><button>生成方案</button>
<button>预览候选</button><button>局部微调</button><button>保存图库</button><button>同步 Listing</button><button>导出记录</button>
</div>
</body></html>
""" + ("商品 SKU 参考 解构 意图 映射 生成 微调 保存 Product Visual Workbench #0a0a12 #0b0d14 #3b82f6 #8b5cf6\n" * 180)

BAD_HTML = "<!doctype html><html><body><section>商品 生成</section><button>开始</button></body></html>"


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def write_case(root: Path, good: bool) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    for name, content in FOUNDATION_FILES.items():
        (root / name).write_text(content, encoding="utf-8")
    delta = root / ("good-delta.md" if good else "bad-delta.md")
    proto = root / ("good.html" if good else "bad.html")
    delta.write_text(GOOD_DELTA if good else BAD_DELTA, encoding="utf-8")
    proto.write_text(GOOD_HTML if good else BAD_HTML, encoding="utf-8")
    return delta, proto


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        good_delta, good_proto = write_case(root / "good", True)
        bad_delta, bad_proto = write_case(root / "bad", False)
        good = run([sys.executable, str(SCRIPT), "--workflow", str(root / "good"), "--delta", good_delta.name, "--prototype", good_proto.name, "--format", "text"])
        if good.returncode != 0:
            failures.append("good case should pass:\n" + good.stdout)
        bad = run([sys.executable, str(SCRIPT), "--workflow", str(root / "bad"), "--delta", bad_delta.name, "--prototype", bad_proto.name, "--format", "text"])
        if bad.returncode == 0:
            failures.append("bad case should fail:\n" + bad.stdout)
    status = "PASS" if not failures else "FAIL"
    print(f"status={status} checks=2")
    for failure in failures:
        print(failure)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
