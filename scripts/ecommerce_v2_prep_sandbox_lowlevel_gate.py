#!/usr/bin/env python3
"""SelfCheck gates for Ecommerce V2 Prep/Sandbox low-level regression prevention.

This verifier intentionally catches cheap, repeatedly observed failures:
- stale/internal user-facing copy in source or built bundles;
- fixed four-question flow regressions;
- blocked prompt plans leaking final composed prompt text;
- slot-count/delete regressions;
- prod/public route and bundle drift when browser/evidence groups are requested.

It prints one JSON object and exits 0 on PASS, 2 on BLOCK/FAIL.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

V_ROOT = Path(os.environ.get("SELFCHECK_V_PROJECT_ROOT", "/root/work/v")).expanduser().resolve()
FRONTEND = V_ROOT / "ecommerce-frontend"
BACKEND = V_ROOT / "ecommerce-backend"
SELF_ROOT = Path("/root/work/agentic-selfcheck")
FEATURE = "ecommerce-v2-prep-sandbox-lowlevel"
REPORT_DIR = SELF_ROOT / "reports" / FEATURE
PUBLIC_BASE = "https://agent-ecommerce.com"

FORBIDDEN_USER_COPY = [
    "Keep/Replace/Drop",
    "Conversation Form Skeleton",
    "Submit Mock Inquiry",
    "沟通表单骨架",
    "模拟提交线索",
    "Asset 01",
    "大模型队列",
    "LLM 决策树",
    "LLM Decision Tree",
    "[object Object]",
    "查看原因和下一步",
    "SKU image analysis is empty or low confidence",
    "re-run image analysis before image-plan composition",
]

REQUIRED_USER_COPY = [
    "图片识别结果太弱或为空",
    "还差四问选择",
    "删除该槽位",
    "低可信项已核对",
    "补齐生成条件",
]

UI_SOURCE_GLOBS = [
    "src/**/*.tsx",
    "src/**/*.ts",
]
DIST_GLOBS = [
    "dist/index.html",
    "dist/assets/*.js",
    "dist/assets/*.css",
]


def emit(status: str, kind: str, details: dict, exit_code: int = 0) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"status": status, "kind": kind, "project_root": str(V_ROOT), "details": details}
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    (REPORT_DIR / f"{kind}.json").write_text(content, encoding="utf-8")
    project_report_dir = V_ROOT / "reports" / FEATURE
    project_report_dir.mkdir(parents=True, exist_ok=True)
    (project_report_dir / f"{kind}.json").write_text(content, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(exit_code)


def fail(kind: str, message: str, **details) -> None:
    emit("BLOCK", kind, {"message": message, **details}, 2)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def iter_files(root: Path, globs: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in globs:
        files.extend([p for p in root.glob(pattern) if p.is_file()])
    return sorted(set(files))


def scan_forbidden(files: list[Path], forbidden: list[str]) -> dict[str, list[str]]:
    hits: dict[str, list[str]] = {}
    for path in files:
        text = read(path)
        rel = str(path.relative_to(FRONTEND) if path.is_relative_to(FRONTEND) else path)
        found = [needle for needle in forbidden if needle in text]
        if found:
            hits[rel] = found
    return hits


def scan_required(files: list[Path], required: list[str]) -> dict[str, bool]:
    combined = "\n".join(read(p) for p in files)
    return {needle: (needle in combined) for needle in required}


def check_static() -> None:
    src_files = iter_files(FRONTEND, UI_SOURCE_GLOBS)
    if not src_files:
        fail("static", "frontend source files missing", root=str(FRONTEND))
    forbidden_hits = scan_forbidden(src_files, FORBIDDEN_USER_COPY)
    if forbidden_hits:
        fail("static", "forbidden user-facing copy found in source", hits=forbidden_hits)

    required_presence = scan_required(src_files, REQUIRED_USER_COPY)
    missing_required = [k for k, ok in required_presence.items() if not ok]
    if missing_required:
        fail("static", "required regression copy/controls missing from source", missing=missing_required)

    sandbox = read(FRONTEND / "src/pages/production/SandboxPage.tsx")
    prep = read(FRONTEND / "src/pages/production/PrepHubPage.tsx")
    production_service = read(FRONTEND / "src/services/production.ts")
    store = read(FRONTEND / "src/store/productionStore.ts")
    contact = read(FRONTEND / "src/pages/ContactPage.tsx")
    if "prepCanEnterSandbox" not in prep or "decisionProgress.complete" not in prep or "total >= 4 && effectiveAnswered >= total" not in prep:
        fail("static", "Prep -> Sandbox gate does not obviously require 4/4 fixed choices")
    if "const prepCanEnterSandbox = parsing?.status === 'succeeded' && decisionProgress.complete" not in prep or "&& !parsingQualityWarning" in prep:
        fail("static", "low-confidence warning must be resolved by completed four-question review, not block after 4/4 choices")
    if "parsingQualityReviewedMessage" not in prep or "低可信项已核对" not in prep:
        fail("static", "Prep low-confidence review-resolved message missing")
    fixed_ids = ["sku_product", "sku_background", "reference_product", "reference_background"]
    missing_fixed_ids = [item for item in fixed_ids if item not in production_service]
    if "fixedPromptQuestionSteps" not in production_service or missing_fixed_ids:
        fail("static", "fixed four-question generator is missing required question ids", missing=missing_fixed_ids)
    if "elementId.startsWith('fixed:')" not in production_service or "prompt_slot" not in production_service:
        fail("static", "fixed question submit path must persist prompt_slot via dedicated API path")
    forbidden_prep_tokens = ["skipDecisionTree", "handleSkipDecisionTree", "decisionTreeSkipped", "SkipForward", "跳过"]
    leaked_prep_tokens = [token for token in forbidden_prep_tokens if token in prep]
    if leaked_prep_tokens:
        fail("static", "Prep fixed-question flow still exposes or carries skip/bypass affordance", tokens=leaked_prep_tokens)
    if "disabled={false}" in prep or "disabled={false}" in sandbox:
        fail("static", "hard-coded disabled={false} found; remove inert disabled props")
    if "allow_low_confidence_sku" in sandbox or "sku_manual_intent" in sandbox or "allow_low_confidence_reference" in sandbox or "reference_manual_intent" in sandbox or "继续使用低质量图片" in sandbox or "按低质量图片继续生成方案" in sandbox:
        fail("static", "Sandbox should not expose the removed low-quality continuation module")
    if "补齐生成条件" not in sandbox or "查看原因和下一步" in sandbox:
        fail("static", "Sandbox blocked production CTA label must be polished and action-oriented")
    if "Math.max(imageCount + 1, assetTasks.length + 1)" not in sandbox or "imageCount < 10" not in sandbox:
        fail("static", "Sandbox slot add/delete count guard missing")
    if "任务 01" not in store:
        fail("static", "Store task labels are not localized away from Asset 01")
    if "Submit request" not in contact or "Contact request" not in contact:
        fail("static", "Contact page mock/skeleton copy replacement missing")

    emit("PASS", "static", {
        "source_files_scanned": len(src_files),
        "forbidden_terms": len(FORBIDDEN_USER_COPY),
        "required_copy": required_presence,
    })


def check_api() -> None:
    visualworkflow_dir = BACKEND / "internal/modules/visualworkflow"
    service = "\n".join(
        read(path) for path in sorted(visualworkflow_dir.glob("*.go"))
        if not path.name.endswith("_test.go")
    )
    tests = "\n".join(read(path) for path in sorted(visualworkflow_dir.glob("*_test.go")))
    required_symbols = [
        "mergeIntentSelections",
        "fixedPromptQuestionSelections",
        "sanitizeIntentSelectionsForPrompt",
        "promptCompositionFromIntentFusion",
        "promptFallbackIntentEntry",
        "fanoutTemplateProviderConfig",
        "fanoutDiversityInstruction",
    ]
    missing = [sym for sym in required_symbols if sym not in service]
    if missing:
        fail("api", "visualworkflow prompt/fixed-question guard symbols missing", missing=missing)
    if 'if ready {' not in service or '"composed_prompt_text"' not in service:
        fail("api", "prompt composition ready-only guard not detectable")
    required_tests = [
        "TestCreatePromptPlannerJobDirectlyComposesWeakImageAnalysis",
        "TestMergeIntentSelectionsPreservesFixedPromptQuestions",
        "raw provider payload leaked into prompt variables",
        "TestCreatePromptPlannerJobUsesFallbackWhenManualTextMissing",
        "TestCreateGenerationFanoutIncludesReferenceAssetsAndTemplateSpecificRuntimeParams",
    ]
    missing_tests = [token for token in required_tests if token not in tests]
    if missing_tests:
        fail("api", "regression tests for low-level prompt/selection guards missing", missing=missing_tests)
    emit("PASS", "api", {"symbols": required_symbols, "tests": required_tests})


def fetch(path: str, timeout: int = 20) -> tuple[int, str, str]:
    url = PUBLIC_BASE + path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "ignore")
            return resp.status, resp.geturl(), body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        return e.code, e.geturl(), body


def public_assets_from_login() -> list[str]:
    status, _, html = fetch("/login")
    if status != 200:
        fail("browser", "public /login did not return 200", status=status)
    return sorted(set(re.findall(r"assets/[^\"'<> ]+", html)))


def check_browser() -> None:
    routes = ["/", "/login", "/products/prod_test/production/prep", "/products/prod_test/production/sandbox", "/contact"]
    statuses = {}
    for route in routes:
        status, final_url, body = fetch(route)
        statuses[route] = {"status": status, "final_url": final_url, "has_spa_shell": "Agent Ecommerce" in body and "/assets/" in body}
        if status != 200:
            fail("browser", "public route did not return 200", route=route, status=status, final_url=final_url)
        if not statuses[route]["has_spa_shell"]:
            fail("browser", "public route did not return Ecommerce SPA shell", route=route, status=status, final_url=final_url)

    public_assets = public_assets_from_login()
    public_text = ""
    fetched = []
    for asset in public_assets:
        if asset.endswith(".js"):
            status, _, body = fetch("/" + asset)
            if status == 200:
                fetched.append(asset)
                public_text += body
    public_forbidden = [needle for needle in FORBIDDEN_USER_COPY if needle != "[object Object]" and needle in public_text]
    if public_forbidden:
        fail("browser", "forbidden stale/mock copy found in public JavaScript bundle", forbidden=public_forbidden, fetched=fetched[:20])
    emit("PASS", "browser", {"routes": statuses, "js_assets_scanned": len(fetched)})


def check_evidence() -> None:
    dist_files = iter_files(FRONTEND, DIST_GLOBS)
    if not dist_files:
        fail("evidence", "frontend dist missing; run npm run build before evidence gate")
    bundle_forbidden = [needle for needle in FORBIDDEN_USER_COPY if needle != "[object Object]"]
    forbidden_hits = scan_forbidden(dist_files, bundle_forbidden)
    if forbidden_hits:
        fail("evidence", "forbidden user-facing copy found in built bundle", hits=forbidden_hits)
    required_presence = scan_required(dist_files, ["图片识别结果太弱或为空", "还差四问选择", "低可信项已核对", "补齐生成条件"])
    missing_required = [k for k, ok in required_presence.items() if not ok]
    if missing_required:
        fail("evidence", "required blocker copy missing from built bundle", missing=missing_required)
    removed_low_quality_copy = scan_required(dist_files, ["继续使用低质量图片", "按低质量图片继续生成方案", "allow_low_confidence_sku", "sku_manual_intent", "allow_low_confidence_reference", "reference_manual_intent"])
    present_removed = [k for k, ok in removed_low_quality_copy.items() if ok]
    if present_removed:
        fail("evidence", "removed low-quality continuation module still present in built bundle", present=present_removed)

    # Public deployed bundle smoke: verify the current public login HTML points at new-ish assets
    # and fetch selected known lazy chunks when present. This is evidence, not a substitute for browser E2E.
    public_assets = public_assets_from_login()
    public_text = ""
    for asset in public_assets:
        if asset.endswith(".js"):
            _, _, body = fetch("/" + asset)
            public_text += body
    local_key_chunks = [p.name for p in (FRONTEND / "dist/assets").glob("*.js") if p.name.startswith(("PrepHubPage-", "SandboxPage-", "production-", "ContactPage-", "index-"))]
    fetched_chunks = []
    for name in local_key_chunks:
        try:
            status, _, body = fetch("/assets/" + name)
            if status == 200:
                fetched_chunks.append(name)
                public_text += body
        except Exception:
            pass
    public_forbidden = [needle for needle in FORBIDDEN_USER_COPY if needle != "[object Object]" and needle in public_text]
    if public_forbidden:
        fail("evidence", "forbidden copy found in public deployed bundle", forbidden=public_forbidden)
    removed_public = {needle: (needle in public_text) for needle in ["继续使用低质量图片", "按低质量图片继续生成方案", "allow_low_confidence_sku", "sku_manual_intent", "allow_low_confidence_reference", "reference_manual_intent"]}
    required_public = {needle: (needle in public_text) for needle in ["图片识别结果太弱或为空", "还差四问选择", "低可信项已核对", "补齐生成条件"]}
    missing_public_required = [needle for needle, present in required_public.items() if not present]

    emit("PASS", "evidence", {
        "dist_files_scanned": len(dist_files),
        "public_assets_from_login": public_assets[:20],
        "public_key_chunks_fetched": fetched_chunks,
        "required_public": required_public,
        "missing_public_required": missing_public_required,
        "public_deploy_note": "Public bundle may lag local verified dist; absence of required copy is non-blocking until an approved production deploy is performed.",
        "removed_public": removed_public,
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["static", "api", "browser", "evidence"], required=True)
    args = ap.parse_args()
    {
        "static": check_static,
        "api": check_api,
        "browser": check_browser,
        "evidence": check_evidence,
    }[args.kind]()


if __name__ == "__main__":
    main()
