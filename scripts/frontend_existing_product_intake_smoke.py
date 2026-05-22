#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

GOOD_PROJECT_CONTEXT = """# Project Context

## Existing product background
Product purpose: Existing ecommerce operations workspace.
Target users: operators and merchants.
Current business workflow: product intake, visual workbench, listing/export.
Where this increment fits in the existing workflow: improves product center review path.
What must remain true after the increment: existing product detail and asset flows stay reachable.

## Current implementation state
Existing routes/pages affected: ecommerce-frontend/src/App.tsx and src/pages/ProductCenter.tsx.
Existing components/layouts/shells to preserve: authenticated shell, product cards, detail navigation.
Existing service/API/data contracts: product list/detail APIs, asset APIs, visual workflow APIs.
Existing states already implemented: loading, empty, list, detail, error.
Known missing capabilities, marked `contract-needed`: batch visual refinement callback needs backend extension.

## Current visual and interaction baseline
Theme / color / typography / spacing direction: dark commerce workbench with blue/violet accents.
Navigation shell and page chrome: existing Ecommerce shell and user menu.
Existing cards/tables/drawers/modals/steppers patterns: cards, side drawers, workflow stepper.
Reference screenshots from the live/current product: reference-screenshots/current-product-center.png.
What visual style must not be broken: dark shell, dense operations layout, clear product hierarchy.

## System feasibility map
Major visible functions are mapped in API_BACKEND_FEASIBILITY_MAP.md with existing frontend and backend support.

## User-facing product UI boundary
Forbidden in user-facing prototype UI: internal governance terms, backend/API gap wording, gate/verifier/coverage wording.
Translate internal state into user language: unavailable capability becomes limited product state, not engineering jargon.

## Prototype grounding rule
The prototype must preserve the existing product shell, routes, data contracts and business workflow while improving clarity.
"""

GOOD_BASELINE = """# Existing Product Baseline

## Product identity
Product name: Agent Ecommerce.
Product purpose: Generate and manage commerce product assets.
Target users: operators and merchants.
Existing business workflow: product intake -> visual workbench -> listing/export.
Current release / maturity reality: product center and visual workflow are partially implemented.

## Route and surface inventory
| Route / surface | Current purpose | Existing user actions | Current state quality | Evidence path |
|---|---|---|---|---|
| /products | Product list | open detail, filter, inspect assets | implemented | reference-screenshots/products.png |
| /products/:id | Product detail | review SKU, assets, listing state | implemented | reference-screenshots/detail.png |

## Current visual baseline
Color / theme / tone: dark operational workbench with blue/violet accents.
Typography / spacing / density: compact enterprise dashboard density.
Navigation shell: existing Ecommerce authenticated shell.
Card / table / drawer / modal / stepper patterns: cards, tables, detail drawer and stepper.
Interaction motion / feedback patterns: clear selected, loading and retry states.
What visual style must not regress: dark shell and product hierarchy.

## Existing constraints
Existing components/layouts to preserve: shell, auth menu, product cards.
Existing API/client/service layer to use: ecommerce service layer.
Auth / role / data-sensitivity constraints: no token or internal IDs in UI.
Mobile/i18n/accessibility constraints: responsive and localized copy.
Known technical or product debt: visual workflow backend is partial.

## Baseline evidence
Current screenshots: reference-screenshots/products.png and detail.png.
Current routes inspected: /products, /products/:id.
Current code/docs inspected: ecommerce-frontend docs and services.
Live/browser evidence if available: browser-evidence/current-product-center.json.
"""

GOOD_API = """# API / Backend Feasibility Map

| Visible user function | Existing frontend support | Existing backend/API/data support | Required adaptation / contract-needed | Prototype UI treatment |
|---|---|---|---|---|
| Product list review | ProductCenter route and service | product list API supported | none | normal product list |
| Visual generation status | Visual workflow panel partial | visual workflow stage-view partial | contract-needed: refinement callback | show pending/limited state with user-safe copy |

## Backend impact summary
Existing endpoints reused: product list/detail, asset list, visual workflow stage-view.
New/changed endpoints needed: refinement callback and generated asset writeback.
Data model changes needed: generation version metadata.
Async/job/state-machine changes needed: provider callback state projection.
Billing/quota/security/permission implications: preserve existing wallet/quota gates.
Migration/compatibility implications: keep product detail asset compatibility.
"""

GOOD_LANG = """# Product Surface Language Rules

## Forbidden user-visible terms
Do not show internal review, gate, verifier, coverage, contract-needed, backend gap, model provider, GPU, TFlops, Stage, V1, V2, V3.

## Translation rules
| Internal concept | User-facing language |
|---|---|
| contract-needed | 暂未开放 |
| backend job pending | 正在处理 |
| API unavailable | 暂不可用 |
| intent spec | 生成方向 |

## Requirement
Every prototype artifact must be scanned for forbidden internal language before user review.
"""

GOOD_TRACE = """# Prototype Requirement Trace

| Requirement / source anchor | Prototype surface | Interaction / state | Backend/API feasibility | Evidence path | Status |
|---|---|---|---|---|---|
| Product list clarity | /products | list, filter, select | supported | prototype-screenshots/list.png | PASS |
| Visual generation status | /products/:id/visual | pending, success, retry | partial / contract-needed | prototype-screenshots/visual.png | PASS |
| Export handoff | /products/:id/export | review export readiness | supported | prototype-screenshots/export.png | PASS |
| Asset saveback | /products/:id/assets | saved/synced state | partial / contract-needed | prototype-screenshots/assets.png | PASS |
| Error recovery | /products/:id/visual | failed/retry | supported | prototype-screenshots/retry.png | PASS |

## Non-regression rule
For existing-product iterations, do not regress current working product paths unless the tradeoff is explicitly accepted by the human reviewer.

Preserved existing surfaces: product list, product detail, asset list.
Changed existing surfaces: visual workflow panel.
New surfaces: refined visual workbench.
Removed/weakened surfaces and accepted tradeoff: none.
"""

GOOD_PROTO = "<html><body><main><h1>Product Center</h1><button>Navigate to details</button><p>正在处理商品素材，请稍后查看候选方案。</p></main></body></html>"
BAD_PROTO = "<html><body><main><h1>Product Center</h1><p>contract-needed backend gap gate coverage model provider</p></main></body></html>"
BAD_ATTR_PROTO = "<html><body><main><img alt='backend gap gate coverage contract-needed model provider GPU' src='x.png'><input value='contract-needed'></main></body></html>"


def write_good_workflow(root: Path, name: str) -> Path:
    wf = root / ".hermes/workflows" / name
    if wf.exists(): shutil.rmtree(wf)
    wf.mkdir(parents=True)
    (wf / "PROJECT_CONTEXT.md").write_text(GOOD_PROJECT_CONTEXT, encoding="utf-8")
    (wf / "EXISTING_PRODUCT_BASELINE.md").write_text(GOOD_BASELINE, encoding="utf-8")
    (wf / "API_BACKEND_FEASIBILITY_MAP.md").write_text(GOOD_API, encoding="utf-8")
    (wf / "PRODUCT_SURFACE_LANGUAGE_RULES.md").write_text(GOOD_LANG, encoding="utf-8")
    (wf / "PROTOTYPE_REQUIREMENT_TRACE.md").write_text(GOOD_TRACE, encoding="utf-8")
    (wf / "prototype-artifacts").mkdir()
    (wf / "prototype-artifacts/good.html").write_text(GOOD_PROTO, encoding="utf-8")
    (wf / "prototype-artifacts/bad.html").write_text(BAD_PROTO, encoding="utf-8")
    (wf / "prototype-artifacts/bad-attrs.html").write_text(BAD_ATTR_PROTO, encoding="utf-8")
    return wf


def run(root: Path, cmd: list[str], should_pass: bool, case: str) -> dict:
    cp = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    passed = cp.returncode == 0
    no_traceback = "Traceback" not in cp.stdout and "Traceback" not in cp.stderr
    return {"case": case, "expected": "PASS" if should_pass else "FAIL", "actual": "PASS" if passed else "FAIL", "returncode": cp.returncode, "ok": passed == should_pass and no_traceback, "stdout": cp.stdout[-1600:], "stderr": cp.stderr[-1600:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    good = write_good_workflow(root, "frontend-existing-product-intake-smoke-good")
    missing = write_good_workflow(root, "frontend-existing-product-intake-smoke-missing")
    (missing / "API_BACKEND_FEASIBILITY_MAP.md").unlink()
    thin = write_good_workflow(root, "frontend-existing-product-intake-smoke-thin")
    (thin / "EXISTING_PRODUCT_BASELINE.md").write_text("TODO\n", encoding="utf-8")
    cases = [
        run(root, ["scripts/frontend_existing_product_intake_gate.py", "--root", ".", "--workflow", str(good), "--risk", "D", "--prototype", "prototype-artifacts/good.html", "--format", "json"], True, "good-existing-product-intake"),
        run(root, ["scripts/frontend_existing_product_intake_gate.py", "--root", ".", "--workflow", str(missing), "--risk", "D", "--format", "json"], False, "bad-missing-api-feasibility"),
        run(root, ["scripts/frontend_existing_product_intake_gate.py", "--root", ".", "--workflow", str(thin), "--risk", "D", "--format", "json"], False, "bad-thin-baseline"),
        run(root, ["scripts/frontend_existing_product_intake_gate.py", "--root", ".", "--workflow", str(good), "--risk", "D", "--prototype", "prototype-artifacts/bad.html", "--format", "json"], False, "bad-user-ui-internal-language"),
        run(root, ["scripts/frontend_existing_product_intake_gate.py", "--root", ".", "--workflow", str(good), "--risk", "D", "--prototype", "prototype-artifacts/bad-attrs.html", "--format", "json"], False, "bad-user-ui-attribute-internal-language"),
        run(root, ["scripts/frontend_existing_product_intake_gate.py", "--root", ".", "--workflow", "/tmp/outside-workflow", "--risk", "D", "--format", "json"], False, "bad-workflow-outside-root"),
    ]
    ok = all(c["ok"] for c in cases)
    payload = {"status": "PASS" if ok else "FAIL", "cases": cases}
    if args.format == "json": print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("status=" + payload["status"])
        for c in cases: print(f"{c['case']}: expected {c['expected']} actual {c['actual']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
