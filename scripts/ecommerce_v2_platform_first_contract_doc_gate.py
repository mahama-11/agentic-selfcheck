#!/usr/bin/env python3
"""Deterministic doc/evidence gate for Ecommerce V2 platform-first landing.

This gate intentionally stays static/docs-only. It validates that the workflow
handoff documents exist and contain the core cross-boundary vocabulary for the
first platform-first tranche, the narrow runtime-readiness integration tranche,
and the frontend stage-view contract-consumption tranche without running product
code or browser/runtime checks.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


RUNTIME_READINESS_WORKFLOW = "/root/work/v/.hermes/workflows/ecommerce-v2-runtime-readiness-integration"
FRONTEND_STAGEVIEW_WORKFLOW = "/root/work/v/.hermes/workflows/ecommerce-v2-frontend-stageview-contract"
INTENT_PROMPT_WORKFLOW = "/root/work/v/.hermes/workflows/ecommerce-v2-intent-prompt-plan-persistence"
FRONTEND_STAGEVIEW_ROOT = "/root/work/v-worktrees/ecommerce-v2-frontend-stageview-contract/ecommerce-frontend"
ECOMMERCE_BACKEND_ROOT = "/root/work/v-worktrees/ecommerce-v2-visualworkflow-s1-s2/ecommerce-backend"

REQUIRED_DOCS = {
    "01-requirement.md": [
        "platform-first",
        "ecommerce v2",
        "runtime capability",
        "visualworkflow",
        "contract-needed",
    ],
    "02a-platform-architecture-review.md": [
        "runtime capability",
        "task type",
        "storage",
        "quota",
        "metering",
        "contract-needed",
        "workflow stage semantics",
    ],
    "02b-ecommerce-architecture-review.md": [
        "visualworkflow",
        "source reference",
        "deconstruction",
        "stage-view",
        "product center",
        "provider-specific APIs",
    ],
    "02c-selfcheck-integration-plan.md": [
        "ecommerce-v2-platform-first-landing",
        "v-workspace",
        "static,evidence",
        "ecommerce-v2-platform-first-contract-doc-gate",
        "provider/crawler/video/inpainting",
    ],
    "03-implementation-plan.md": [
        "platform p0",
        "ecommerce backend s1+s2",
        "selfcheck feature/gate scaffolding",
        "features/ecommerce-v2-platform-first-landing.yaml",
        "do not wire broad runtime/browser gates yet",
    ],
}

RUNTIME_READINESS_REQUIRED_DOCS = {
    "01-requirement.md": [
        "runtime readiness integration",
        "GET /internal/v1/runtime/capabilities?product_code=ecommerce",
        "visualworkflow",
        "stage-view",
        "contract-needed",
        "Do not call providers",
    ],
    "02-architecture-review.md": [
        "ListRuntimeCapabilities",
        "runtime_capabilities",
        "PLATFORM_CAPABILITY_UNAVAILABLE",
        "PLATFORM_CAPABILITY_ERROR",
        "CONTRACT_NEEDED",
        "Do not expose provider secrets",
    ],
    "03-implementation-plan.md": [
        "platform.Client",
        "ListRuntimeCapabilities",
        "runtime_capabilities",
        "SelfCheck acceptance",
        "without wiring broad api/browser/runtime groups",
    ],
}

FRONTEND_STAGEVIEW_REQUIRED_DOCS = {
    "01-requirement.md": [
        "Frontend Stage-view Contract Consumption",
        "runtime_capabilities",
        "runtime_capability_error",
        "PLATFORM_CAPABILITY_UNAVAILABLE",
        "PLATFORM_CAPABILITY_ERROR",
        "CONTRACT_NEEDED",
        "contract-needed",
        "mock",
    ],
    "02-architecture-review.md": [
        "src/services/visualWorkflow.ts",
        "src/types/visualWorkflow.ts",
        "ProductVisualToolsPage.tsx",
        "stage-view",
        "runtime_capabilities",
        "runtime_capability_error",
        "Platform internal runtime capability APIs",
        "mock capability matrices",
    ],
}

FRONTEND_OPTIONAL_EVIDENCE_DOCS = {
    "04-developer-summary.md": ["stage-view", "runtime_capabilities", "typecheck", "build"],
    "04b-selfcheck-developer-summary.md": ["SelfCheck", "frontend stage-view", "static/evidence"],
    "05-spec-review-report.md": ["stage-view", "contract"],
    "06-quality-review-report.md": ["runtime_capabilities", "mock"],
    "07-qa-report.md": ["PASS", "SelfCheck"],
    "08-final-verification.md": ["final", "stage-view"],
}

INTENT_PROMPT_REQUIRED_DOCS = {
    "01-requirement.md": ["intent_spec", "prompt_plan", "Prompt Center", "compiled prompt", "provider execution"],
    "02-architecture-review.md": ["IntentSpecDTO", "PromptPlanDTO", "Prompt Center owns", "compiled prompt", "source_map", "content hash", "CONTRACT_NEEDED"],
    "03-implementation-plan.md": ["IntentSpecDTO", "PromptPlanDTO", "Prompt Center-safe boundary", "go test ./internal/modules/visualworkflow", "No provider execution"],
    "04-developer-summary.md": ["IntentSpecDTO", "PromptPlanDTO", "Prompt Center-safe boundary", "go test ./...", "No Prompt Center Preview call"],
}

INTENT_PROMPT_OPTIONAL_EVIDENCE_DOCS = {
    "05-spec-review-report.md": ["APPROVE", "intent_spec", "prompt_plan", "Prompt Center"],
    "06-quality-review-report.md": ["APPROVE", "Prompt Center", "provider", "CONTRACT_NEEDED"],
    "07-qa-report.md": ["PASS", "go test", "selfcheck"],
    "08-final-verification.md": ["PASS", "ecommerce-v2-intent-prompt-plan-persistence"],
}

INTENT_PROMPT_CROSS_DOC_TERMS = [
    "visual workflow session",
    "stage-view",
    "intent_spec",
    "prompt_plan",
    "prompt_id",
    "Prompt Center owns",
    "compiled prompt",
    "source_map",
    "content_hash",
    "source_map_hash",
    "CONTRACT_NEEDED",
    "no provider execution",
    "no fake",
]

BACKEND_INTENT_PROMPT_FILES = {
    "internal/modules/visualworkflow/types.go": ["type IntentSpecDTO struct", "type PromptPlanDTO struct", "func (p *PromptPlanDTO) UnmarshalJSON", "validatePromptPlanForbiddenKeys", "json:\"intent_spec\"", "json:\"prompt_plan\""],
    "internal/modules/visualworkflow/service.go": ["defaultIntentSpec", "defaultPromptPlan", "encodeIntentSpec", "decodePromptPlan", "validatePromptPlan", "isForbiddenPromptPlanKey", "compiled_prompt", "source_map_hash", "provider_response"],
    "internal/modules/visualworkflow/mapper.go": ["decodeIntentSpec", "decodePromptPlan", "applyPromptAndGenerationContractReadiness", "prompt_plan", "generation", "CONTRACT_NEEDED"],
    "internal/modules/visualworkflow/service_test.go": ["TestVisualWorkflowPersistsTypedIntentSpecAndPromptPlan", "TestSessionHandlersProjectTypedIntentSpecAndPromptPlan", "TestPromptPlanRejectsPromptCenterArtifactsAndDoesNotLeak", "compiled_prompt", "source_map", "content_hash", "provider_response"],
    "internal/migration/migration.go": ["visual_workflow_intent_prompt_plan_columns", "EcommerceVisualWorkflowSession"],
}

CROSS_DOC_TERMS = [
    "image_understanding",
    "ocr",
    "image_generation",
    "image_inpainting",
    "video_keyframe",
    "GET /internal/v1/runtime/capabilities?product_code=ecommerce",
    "contract-needed",
    "visual workflow session",
    "source reference",
    "deconstruction element",
    "session_id",
    "product_id",
    "sku_code",
    "current_stage",
    "readiness",
    "generation_versions",
    "no real provider integration",
]

RUNTIME_READINESS_CROSS_DOC_TERMS = [
    "ListRuntimeCapabilities",
    "runtime_capabilities",
    "PLATFORM_CAPABILITY_UNAVAILABLE",
    "PLATFORM_CAPABILITY_ERROR",
    "GET /internal/v1/runtime/capabilities?product_code=ecommerce",
    "image_understanding",
    "image_generation",
    "image_inpainting",
    "video_keyframe",
    "contract-needed",
    "stage-view",
    "readiness",
    "no real deconstruction provider execution",
]

FRONTEND_STAGEVIEW_CROSS_DOC_TERMS = [
    "GET /api/v1/ecommerce/v2/visual-workflows/:session_id/stage-view",
    "POST /api/v1/ecommerce/products/:product_id/v2/visual-sessions",
    "GET /api/v1/ecommerce/v2/visual-workflows/sessions",
    "runtime_capabilities",
    "runtime_capability_error",
    "PLATFORM_CAPABILITY_UNAVAILABLE",
    "PLATFORM_CAPABILITY_ERROR",
    "CONTRACT_NEEDED",
    "contract-needed",
    "raw",
    "mock capability",
]

FEATURE_REQUIRED_TERMS = [
    "id: ecommerce-v2-platform-first-landing",
    "project: v-workspace",
    "ecommerce-v2-platform-first-contract-doc-gate",
    "evidence-gate",
]

VERIFIER_REQUIRED_TERMS = [
    "id: ecommerce-v2-platform-first-contract-doc-gate",
    "kind: static",
    "scripts/ecommerce_v2_platform_first_contract_doc_gate.py",
    RUNTIME_READINESS_WORKFLOW,
    FRONTEND_STAGEVIEW_WORKFLOW,
    INTENT_PROMPT_WORKFLOW,
    ECOMMERCE_BACKEND_ROOT,
]

FRONTEND_TYPE_REQUIRED_TERMS = [
    "VisualWorkflowStageViewDTO",
    "VisualWorkflowSessionDTO",
    "VisualWorkflowRuntimeCapabilityDTO",
    "VisualWorkflowRuntimeCapabilityErrorDTO",
    "runtime_capabilities",
    "runtime_capability_error",
    "CONTRACT_NEEDED",
    "PLATFORM_CAPABILITY_UNAVAILABLE",
    "PLATFORM_CAPABILITY_ERROR",
    "contract-needed",
]

FRONTEND_SERVICE_REQUIRED_TERMS = [
    "request<",
    "VisualWorkflowStageViewDTO",
    "createVisualWorkflowSession",
    "listVisualWorkflowSessions",
    "getVisualWorkflowStageView",
    "/api/v1/ecommerce/products/",
    "/v2/visual-sessions",
    "/api/v1/ecommerce/v2/visual-workflows/sessions",
    "/api/v1/ecommerce/v2/visual-workflows/",
    "/stage-view",
    "product_id",
    "sku_code",
]

FRONTEND_UI_REQUIRED_TERMS = [
    "listVisualWorkflowSessions",
    "getVisualWorkflowStageView",
    "runtime_capabilities",
    "runtime_capability_error",
    "CONTRACT_NEEDED",
    "PLATFORM_CAPABILITY_UNAVAILABLE",
    "PLATFORM_CAPABILITY_ERROR",
    "contract-needed",
]

FRONTEND_DOC_REQUIRED_TERMS = [
    "src/services/visualWorkflow.ts",
    "stage-view",
    "runtime_capabilities",
    "runtime_capability_error",
    "mock",
]


class Failure:
    def __init__(self, path: Path | str, message: str) -> None:
        self.path = str(path)
        self.message = message

    def __str__(self) -> str:
        return f"FAIL: {self.path}: {self.message}"


def read_text(path: Path, failures: list[Failure]) -> str:
    if not path.exists():
        failures.append(Failure(path, "missing required file"))
        return ""
    if not path.is_file():
        failures.append(Failure(path, "required path is not a file"))
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        failures.append(Failure(path, f"not valid UTF-8: {exc}"))
        return ""
    if not text.strip():
        failures.append(Failure(path, "file is empty"))
    return text


def require_terms(path: Path | str, text: str, terms: list[str], failures: list[Failure]) -> None:
    folded = text.casefold()
    for term in terms:
        if term.casefold() not in folded:
            failures.append(Failure(path, f"missing required term: {term}"))


def require_absent(path: Path, text: str, terms: list[str], failures: list[Failure], message: str) -> None:
    folded = text.casefold()
    for term in terms:
        if term.casefold() in folded:
            failures.append(Failure(path, f"{message}: {term}"))


def iter_text_files(root: Path, relative_root: str) -> list[Path]:
    base = root / relative_root
    if not base.exists():
        return []
    return [p for p in base.rglob("*") if p.is_file() and p.suffix in {".ts", ".tsx", ".md"}]


def contains_any(text: str, terms: list[str]) -> bool:
    folded = text.casefold()
    return any(term.casefold() in folded for term in terms)


def validate_intent_prompt_backend_code(backend_root: Path, failures: list[Failure]) -> None:
    if not backend_root.exists():
        failures.append(Failure(backend_root, "ecommerce backend worktree is missing"))
        return
    for rel_path, terms in BACKEND_INTENT_PROMPT_FILES.items():
        path = backend_root / rel_path
        text = read_text(path, failures)
        require_terms(path, text, terms, failures)
    visualworkflow_text = "\n".join(
        read_text(backend_root / rel_path, failures)
        for rel_path in [
            "internal/modules/visualworkflow/types.go",
            "internal/modules/visualworkflow/service.go",
            "internal/modules/visualworkflow/mapper.go",
        ]
    )
    require_absent(
        backend_root / "internal/modules/visualworkflow",
        visualworkflow_text,
        ["promptcenter", "Preview("],
        failures,
        "visualworkflow must not execute or directly couple to Prompt Center preview in this tranche",
    )


def validate_frontend_stageview_code(frontend_root: Path, failures: list[Failure]) -> None:
    if not frontend_root.exists():
        failures.append(Failure(frontend_root, "frontend stage-view worktree is missing"))
        return

    src = frontend_root / "src"
    if not src.exists():
        failures.append(Failure(src, "frontend src directory is missing"))
        return

    type_path = src / "types" / "visualWorkflow.ts"
    service_path = src / "services" / "visualWorkflow.ts"
    type_text = read_text(type_path, failures)
    service_text = read_text(service_path, failures)
    require_terms(type_path, type_text, FRONTEND_TYPE_REQUIRED_TERMS, failures)
    require_terms(service_path, service_text, FRONTEND_SERVICE_REQUIRED_TERMS, failures)
    require_absent(
        service_path,
        service_text,
        ["fetch(", "axios", "/internal/v1/runtime/capabilities"],
        failures,
        "visual workflow service must use product backend service boundary only",
    )

    page_path = src / "pages" / "ProductVisualToolsPage.tsx"
    page_text = read_text(page_path, failures)
    if "VisualWorkflowStageViewPanel" not in page_text and "getVisualWorkflowStageView" not in page_text:
        failures.append(Failure(page_path, "stage-view UI component/page reference is missing"))

    ui_candidates = [
        page_path,
        src / "pages" / "product" / "components" / "VisualWorkflowStageViewPanel.tsx",
        src / "components" / "VisualWorkflowStageViewPanel.tsx",
    ]
    ui_texts: list[str] = []
    existing_ui_candidates: list[Path] = []
    for candidate in ui_candidates:
        if candidate.exists():
            existing_ui_candidates.append(candidate)
            ui_texts.append(read_text(candidate, failures))
    if not existing_ui_candidates:
        failures.append(Failure(src / "pages" / "ProductVisualToolsPage.tsx", "missing stage-view UI integration target"))
    else:
        combined_ui = "\n".join(ui_texts)
        require_terms("frontend stage-view UI", combined_ui, FRONTEND_UI_REQUIRED_TERMS, failures)

    docs_path = frontend_root / "docs" / "DEVELOPER_GUIDE.md"
    if docs_path.exists():
        docs_text = read_text(docs_path, failures)
        require_terms(docs_path, docs_text, FRONTEND_DOC_REQUIRED_TERMS, failures)
    else:
        failures.append(Failure(docs_path, "frontend developer guide is missing stage-view contract documentation target"))

    for code_path in iter_text_files(frontend_root, "src"):
        text = read_text(code_path, failures)
        require_absent(
            code_path,
            text,
            ["/internal/v1/runtime/capabilities", "GET /internal/v1/runtime/capabilities"],
            failures,
            "frontend must not call Platform internal runtime capability APIs directly",
        )

    mock_root = src / "mock"
    for mock_path in iter_text_files(frontend_root, "src/mock"):
        mock_text = read_text(mock_path, failures)
        forbidden_mock_terms = [
            "runtime_capabilities",
            "runtimeCapability",
            "PLATFORM_CAPABILITY_UNAVAILABLE",
            "PLATFORM_CAPABILITY_ERROR",
            "CONTRACT_NEEDED",
            "contract-needed",
            "capabilityMatrix",
            "capability matrix",
        ]
        if contains_any(mock_text, forbidden_mock_terms):
            failures.append(
                Failure(mock_path, f"mock capability matrix or mocked stage-view capability evidence is forbidden under {mock_root}")
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate Ecommerce V2 platform-first workflow docs and static SelfCheck scaffolding.")
    parser.add_argument(
        "--workflow",
        default="/root/work/v/.hermes/workflows/ecommerce-v2-platform-first-landing",
        help="First-tranche workflow evidence directory to inspect.",
    )
    parser.add_argument(
        "--runtime-readiness-workflow",
        default=RUNTIME_READINESS_WORKFLOW,
        help="Second-tranche runtime-readiness workflow evidence directory to inspect.",
    )
    parser.add_argument(
        "--frontend-stageview-workflow",
        default=FRONTEND_STAGEVIEW_WORKFLOW,
        help="Third-tranche frontend stage-view contract workflow evidence directory to inspect.",
    )
    parser.add_argument(
        "--intent-prompt-workflow",
        default=INTENT_PROMPT_WORKFLOW,
        help="Fourth-tranche Ecommerce backend intent/prompt-plan workflow evidence directory to inspect.",
    )
    parser.add_argument(
        "--frontend-root",
        default=FRONTEND_STAGEVIEW_ROOT,
        help="Frontend worktree/root containing stage-view contract consumer code.",
    )
    parser.add_argument(
        "--ecommerce-backend-root",
        default=ECOMMERCE_BACKEND_ROOT,
        help="Ecommerce backend worktree/root containing visualworkflow code.",
    )
    parser.add_argument(
        "--selfcheck-root",
        default=".",
        help="Agentic SelfCheck root containing feature/verifier scaffolding.",
    )
    args = parser.parse_args()

    workflow = Path(args.workflow).resolve()
    runtime_workflow = Path(args.runtime_readiness_workflow).resolve()
    frontend_workflow = Path(args.frontend_stageview_workflow).resolve()
    intent_prompt_workflow = Path(args.intent_prompt_workflow).resolve()
    frontend_root = Path(args.frontend_root).resolve()
    ecommerce_backend_root = Path(args.ecommerce_backend_root).resolve()
    selfcheck_root = Path(args.selfcheck_root).resolve()
    failures: list[Failure] = []

    if not workflow.exists():
        failures.append(Failure(workflow, "workflow directory is missing"))
    if not runtime_workflow.exists():
        failures.append(Failure(runtime_workflow, "runtime-readiness workflow directory is missing"))
    if not frontend_workflow.exists():
        failures.append(Failure(frontend_workflow, "frontend stage-view workflow directory is missing"))
    if not intent_prompt_workflow.exists():
        failures.append(Failure(intent_prompt_workflow, "intent/prompt-plan workflow directory is missing"))
    if not selfcheck_root.exists():
        failures.append(Failure(selfcheck_root, "selfcheck root is missing"))

    combined_docs: list[str] = []
    for name, terms in REQUIRED_DOCS.items():
        path = workflow / name
        text = read_text(path, failures)
        require_terms(path, text, terms, failures)
        combined_docs.append(text)

    combined_text = "\n".join(combined_docs)
    require_terms(workflow, combined_text, CROSS_DOC_TERMS, failures)

    runtime_docs: list[str] = []
    for name, terms in RUNTIME_READINESS_REQUIRED_DOCS.items():
        path = runtime_workflow / name
        text = read_text(path, failures)
        require_terms(path, text, terms, failures)
        runtime_docs.append(text)

    runtime_combined_text = "\n".join(runtime_docs)
    require_terms(runtime_workflow, runtime_combined_text, RUNTIME_READINESS_CROSS_DOC_TERMS, failures)

    frontend_docs: list[str] = []
    for name, terms in FRONTEND_STAGEVIEW_REQUIRED_DOCS.items():
        path = frontend_workflow / name
        text = read_text(path, failures)
        require_terms(path, text, terms, failures)
        frontend_docs.append(text)
    frontend_combined_text = "\n".join(frontend_docs)
    require_terms(frontend_workflow, frontend_combined_text, FRONTEND_STAGEVIEW_CROSS_DOC_TERMS, failures)
    for name, terms in FRONTEND_OPTIONAL_EVIDENCE_DOCS.items():
        path = frontend_workflow / name
        if path.exists():
            require_terms(path, read_text(path, failures), terms, failures)

    validate_frontend_stageview_code(frontend_root, failures)

    intent_prompt_docs: list[str] = []
    for name, terms in INTENT_PROMPT_REQUIRED_DOCS.items():
        path = intent_prompt_workflow / name
        text = read_text(path, failures)
        require_terms(path, text, terms, failures)
        intent_prompt_docs.append(text)
    intent_prompt_combined_text = "\n".join(intent_prompt_docs)
    require_terms(intent_prompt_workflow, intent_prompt_combined_text, INTENT_PROMPT_CROSS_DOC_TERMS, failures)
    for name, terms in INTENT_PROMPT_OPTIONAL_EVIDENCE_DOCS.items():
        path = intent_prompt_workflow / name
        if path.exists():
            require_terms(path, read_text(path, failures), terms, failures)
    validate_intent_prompt_backend_code(ecommerce_backend_root, failures)

    feature_path = selfcheck_root / "features" / "ecommerce-v2-platform-first-landing.yaml"
    verifier_path = selfcheck_root / "verifiers" / "ecommerce-v2-platform-first-contract-doc-gate.yaml"
    script_path = selfcheck_root / "scripts" / "ecommerce_v2_platform_first_contract_doc_gate.py"

    feature_text = read_text(feature_path, failures)
    verifier_text = read_text(verifier_path, failures)
    read_text(script_path, failures)
    require_terms(feature_path, feature_text, FEATURE_REQUIRED_TERMS, failures)
    require_terms(verifier_path, verifier_text, VERIFIER_REQUIRED_TERMS, failures)

    forbidden_feature_terms = ["browser:", "runtime:", "api:"]
    for term in forbidden_feature_terms:
        if term.casefold() in feature_text.casefold():
            failures.append(Failure(feature_path, f"first tranche must not wire broad gate group: {term}"))

    for term in forbidden_feature_terms:
        if term.casefold() in verifier_text.casefold():
            failures.append(Failure(verifier_path, f"focused gate must not wire broad gate group: {term}"))
    if failures:
        for failure in failures:
            print(failure)
        return 1

    print("PASS: Ecommerce V2 platform-first + runtime-readiness + frontend stage-view + intent/prompt-plan doc/evidence gate passed")
    print(f"checked_workflow={workflow}")
    print(f"checked_runtime_readiness_workflow={runtime_workflow}")
    print(f"checked_frontend_stageview_workflow={frontend_workflow}")
    print(f"checked_intent_prompt_workflow={intent_prompt_workflow}")
    print(f"checked_frontend_root={frontend_root}")
    print(f"checked_ecommerce_backend_root={ecommerce_backend_root}")
    print(f"checked_selfcheck_root={selfcheck_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
