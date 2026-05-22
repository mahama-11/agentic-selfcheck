#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_TEMPLATE = Path("templates/frontend/workflow-state/FRONTEND_WORKFLOW_STATE.json")
MANIFEST_TEMPLATE = Path("templates/frontend/evidence-manifest/FRONTEND_EVIDENCE_MANIFEST.json")
ADAPTER_TEMPLATE = Path("templates/frontend/project-adapter/PROJECT_ADAPTER.yaml")
EXISTING_PRODUCT_INTAKE_TEMPLATES = [
    Path("templates/frontend/existing-product-intake/EXISTING_PRODUCT_BASELINE.md"),
    Path("templates/frontend/existing-product-intake/API_BACKEND_FEASIBILITY_MAP.md"),
    Path("templates/frontend/existing-product-intake/PRODUCT_SURFACE_LANGUAGE_RULES.md"),
    Path("templates/frontend/existing-product-intake/PROTOTYPE_REQUIREMENT_TRACE.md"),
    Path("templates/frontend/prototype-iteration-policy/PROTOTYPE_ITERATION_POLICY.md"),
    Path("templates/frontend/prototype-foundation-ledger/PROTOTYPE_FOUNDATION_LEDGER.md"),
]


def slugify(value: str) -> str:
    raw = value.strip()
    if not raw or raw.startswith(('/', '.')) or '/' in raw or '\\' in raw or '..' in raw:
        raise ValueError("unsafe workflow name")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    slug = re.sub(r"-+", "-", slug)
    if not slug:
        raise ValueError("empty workflow name after slugify")
    return slug


SAFE_SCALAR_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def safe_scalar(value: str, label: str) -> str:
    if not value:
        return value
    if not SAFE_SCALAR_RE.fullmatch(value):
        raise ValueError(f"unsafe {label}")
    return value


def safe_project_root(value: str) -> str:
    value = value or '.'
    if value.startswith('/') or any(part in {'..', ''} for part in value.replace('\\', '/').split('/')):
        raise ValueError("unsafe project root")
    if value != '.' and not SAFE_SCALAR_RE.fullmatch(value):
        raise ValueError("unsafe project root")
    return value


def path_has_symlink(path: Path, stop: Path) -> bool:
    stop = stop.resolve()
    cur = path
    chain = [cur]
    while cur != stop and cur != cur.parent:
        cur = cur.parent
        chain.append(cur)
    return any(p.is_symlink() for p in chain)


def fail(message: str, *, workflow: Path | None = None) -> dict[str, Any]:
    return {"status": "FAIL", "reason": message, "workflow": str(workflow) if workflow else None}


def write_json(path: Path, data: dict[str, Any], *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refuse to overwrite {path}")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_text_template(src: Path, dst: Path, *, force: bool, replacements: dict[str, str] | None = None, header: str = "") -> None:
    if dst.exists() and not force:
        raise FileExistsError(f"refuse to overwrite {dst}")
    text = src.read_text(encoding="utf-8")
    for old, new in (replacements or {}).items():
        text = text.replace(old, new)
    dst.write_text(header + text, encoding="utf-8")


def run_init(root: Path, slug: str, risk: str, project: str, title: str, force: bool) -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        "scripts/init_frontend_workflow.py",
        "--root", str(root),
        "--name", slug,
        "--risk", risk,
        "--project", project,
        "--title", title or slug,
    ]
    if force:
        cmd.append("--force")
    proc = subprocess.run(cmd, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


def bootstrap(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        return 1, fail("root directory does not exist")
    if args.risk not in {"C", "D"}:
        return 1, fail("bootstrap supports only C/D frontend workflows")
    try:
        project = safe_scalar(args.project, "project") if args.project else ""
        project_root = safe_project_root(args.project_root)
    except ValueError as exc:
        return 1, fail(str(exc))
    try:
        slug = slugify(args.name)
    except ValueError as exc:
        return 1, fail(str(exc))
    workflow = root / ".hermes/workflows" / slug
    try:
        workflow.relative_to(root)
    except ValueError:
        return 1, fail("workflow escaped root", workflow=workflow)
    if path_has_symlink(workflow, root):
        return 1, fail("refuse symlinked workflow path", workflow=workflow)
    if workflow.exists() and any(p.is_symlink() for p in workflow.rglob("*")):
        return 1, fail("refuse workflow containing symlinked files", workflow=workflow)
    if workflow.exists() and not args.force:
        return 1, fail("workflow already exists; use --force to overwrite generated files", workflow=workflow)

    for required in [STATE_TEMPLATE, MANIFEST_TEMPLATE, ADAPTER_TEMPLATE, *EXISTING_PRODUCT_INTAKE_TEMPLATES]:
        if not (root / required).exists():
            return 1, fail(f"missing template {required}")

    code, stdout, stderr = run_init(root, slug, args.risk, project, args.title or slug, args.force)
    if code != 0:
        return 1, {"status": "FAIL", "reason": "init_frontend_workflow failed", "stdout": stdout[-2000:], "stderr": stderr[-2000:], "workflow": str(workflow)}

    now = datetime.now(timezone.utc).isoformat()
    header = f"# Generated by frontend_workflow_bootstrap.py at {now}\n"
    copy_text_template(
        root / ADAPTER_TEMPLATE,
        workflow / "PROJECT_ADAPTER.yaml",
        force=args.force,
        header=header,
        replacements={"name: frontend-project": f"name: {project or slug}", "root: .": f"root: {project_root}"},
    )

    state = json.loads((root / STATE_TEMPLATE).read_text(encoding="utf-8"))
    state.update({
        "workflow_id": slug,
        "risk": args.risk,
        "state": "INTAKE",
        "allowed_transitions": ["CONTEXT_READY", "BLOCKED"],
        "project_adapter": "PROJECT_ADAPTER.yaml",
        "design_pack": None,
        "prototype_coverage": None,
        "parity_plan": None,
    })
    write_json(workflow / "FRONTEND_WORKFLOW_STATE.json", state, force=args.force)

    manifest = json.loads((root / MANIFEST_TEMPLATE).read_text(encoding="utf-8"))
    manifest.update({
        "workflow_id": slug,
        "risk": args.risk,
        "project_adapter": "PROJECT_ADAPTER.yaml",
        "design_pack": [],
        "lanes": [],
        "screenshots": [],
        "coverage": None,
        "parity_plan": None,
        "parity_report": None,
        "runtime_evidence": [],
        "review_urls": [],
    })
    write_json(workflow / "FRONTEND_EVIDENCE_MANIFEST.json", manifest, force=args.force)

    for template in EXISTING_PRODUCT_INTAKE_TEMPLATES:
        copy_text_template(
            root / template,
            workflow / template.name,
            force=args.force,
            header=header,
        )

    guide = workflow / "BOOTSTRAP_NEXT_STEPS.md"
    if args.force or not guide.exists():
        guide.write_text(f"""# Frontend Workflow Bootstrap Next Steps

- Workflow: `{slug}`
- Risk: `{args.risk}`
- Project: `{project or 'unspecified'}`

## Required sequence

```text
context/design pack -> prototype lanes -> screenshots/coverage -> human acceptance -> freeze -> parity plan -> implementation hard stop -> production parity/runtime evidence -> final
```

## First commands

```bash
scripts/frontend_workflow_controller.py status --workflow {workflow} --format text
scripts/frontend_evidence_manifest_gate.py --workflow {workflow} --phase before-user-presentation --format text
```

This workflow is intentionally not implementation-ready at bootstrap time.
""", encoding="utf-8")

    return 0, {
        "status": "PASS",
        "workflow": str(workflow),
        "workflow_id": slug,
        "risk": args.risk,
        "project": project,
        "created": [
            "PROJECT_ADAPTER.yaml",
            "FRONTEND_WORKFLOW_STATE.json",
            "FRONTEND_EVIDENCE_MANIFEST.json",
            "EXISTING_PRODUCT_BASELINE.md",
            "API_BACKEND_FEASIBILITY_MAP.md",
            "PRODUCT_SURFACE_LANGUAGE_RULES.md",
            "PROTOTYPE_REQUIREMENT_TRACE.md",
            "PROTOTYPE_ITERATION_POLICY.md",
            "PROTOTYPE_FOUNDATION_LEDGER.md",
            "BOOTSTRAP_NEXT_STEPS.md",
        ],
        "note": "bootstrap creates intake state only; implementation remains blocked until evidence is complete",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Bootstrap a frontend workflow with state, manifest, adapter, and prototype templates.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--name", required=True)
    ap.add_argument("--risk", required=True)
    ap.add_argument("--project", default="")
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--title", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    code, payload = bootstrap(args)
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"status={payload.get('status')}")
        print(f"workflow={payload.get('workflow')}")
        if payload.get("reason"):
            print(f"reason={payload.get('reason')}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
