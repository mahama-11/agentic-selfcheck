#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

MANIFEST_FILE = "FRONTEND_EVIDENCE_MANIFEST.json"
PHASES = ["before-user-presentation", "before-implementation", "before-final"]
PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD|PLACEHOLDER)\b|`<[^`]+>`|<YYYY|<responsible|<lane-a", re.IGNORECASE)


@dataclass
class GateResult:
    status: str
    workflow: str
    phase: str
    missing: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "workflow": self.workflow, "phase": self.phase, "missing": self.missing, "reasons": self.reasons}


def blocked(workflow: Path, phase: str, reason: str, missing: list[str] | None = None) -> GateResult:
    return GateResult("BLOCKED", str(workflow), phase, missing or [], [reason])


def path_has_symlink(path: Path, stop: Path) -> bool:
    stop = stop.resolve()
    cur = path
    chain = [cur]
    while cur != stop and cur != cur.parent:
        cur = cur.parent
        chain.append(cur)
    return any(p.is_symlink() for p in chain)


def resolve_workflow(root: Path, raw: str) -> tuple[Path, str | None]:
    wf = Path(raw)
    if not wf.is_absolute():
        wf = root / wf
    governed = (root / ".hermes/workflows").resolve()
    resolved = wf.resolve()
    try:
        resolved.relative_to(governed)
    except Exception:
        return resolved, "workflow must stay under governed .hermes/workflows"
    if path_has_symlink(wf, governed):
        return resolved, "workflow path components must not be symlinked"
    return resolved, None


def safe_path(workflow: Path, rel: str, label: str) -> tuple[Path | None, str | None]:
    if not isinstance(rel, str) or not rel.strip():
        return None, f"{label}: missing path"
    if rel.startswith("http://") or rel.startswith("https://"):
        return None, f"{label}: URL is review-only, not local evidence {rel}"
    p = Path(rel)
    candidate = (p if p.is_absolute() else workflow / p).resolve()
    root = workflow.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None, f"{label}: path escapes workflow {rel}"
    return candidate, None


def is_placeholder(path: Path) -> bool:
    text = path.read_text(encoding="utf-8", errors="ignore").strip()
    if len(text) < 30:
        return True
    return bool(PLACEHOLDER_RE.search(text))


def png_valid(data: bytes) -> bool:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return False
    pos = 8
    seen_ihdr = False
    while pos + 12 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        chunk_type = data[pos + 4:pos + 8]
        chunk_data_start = pos + 8
        chunk_data_end = chunk_data_start + length
        crc_end = chunk_data_end + 4
        if crc_end > len(data):
            return False
        expected_crc = struct.unpack(">I", data[chunk_data_end:crc_end])[0]
        actual_crc = zlib.crc32(chunk_type + data[chunk_data_start:chunk_data_end]) & 0xffffffff
        if expected_crc != actual_crc:
            return False
        if chunk_type == b"IHDR":
            if seen_ihdr or length != 13:
                return False
            seen_ihdr = True
        elif chunk_type == b"IEND":
            return seen_ihdr and length == 0 and crc_end == len(data)
        pos = crc_end
    return False


def jpeg_valid(data: bytes) -> bool:
    return len(data) >= 4 and data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")


def webp_valid(data: bytes) -> bool:
    if len(data) < 12 or not (data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
        return False
    declared = struct.unpack("<I", data[4:8])[0]
    return declared + 8 == len(data)


def image_magic_ok(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except OSError:
        return False
    return png_valid(data) or jpeg_valid(data) or webp_valid(data)


def require_file(workflow: Path, rel: str | None, label: str, *, reject_placeholder: bool = True, require_image: bool = False) -> list[str]:
    if rel is None:
        return [f"{label}: missing path"]
    path, err = safe_path(workflow, rel, label)
    if err:
        return [err]
    assert path is not None
    if not path.exists() or not path.is_file():
        return [f"{label}: missing file {rel}"]
    if require_image and not image_magic_ok(path):
        return [f"{label}: not a valid PNG/JPEG/WebP image {rel}"]
    if reject_placeholder and is_placeholder(path):
        return [f"{label}: placeholder or too thin {rel}"]
    return []


def load_manifest(workflow: Path, manifest_rel: str) -> tuple[dict[str, Any] | None, GateResult | None]:
    manifest_path, manifest_err = safe_path(workflow, manifest_rel, "manifest")
    if manifest_err:
        return None, blocked(workflow, "unknown", manifest_err, [manifest_rel])
    assert manifest_path is not None
    if manifest_path.is_symlink():
        return None, blocked(workflow, "unknown", f"refuse symlinked {manifest_rel}", [manifest_rel])
    if not manifest_path.exists():
        return None, blocked(workflow, "unknown", f"missing {manifest_rel}", [manifest_rel])
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, blocked(workflow, "unknown", f"invalid manifest JSON: {exc}", [manifest_rel])
    schema_path = Path(__file__).resolve().parents[1] / "schemas/frontend-evidence-manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.Draft202012Validator(schema).validate(data)
    except jsonschema.ValidationError as exc:
        return None, blocked(workflow, "unknown", f"manifest schema violation: {exc.message}", [manifest_rel])
    return data, None


def check_manifest(workflow: Path, phase: str, manifest_rel: str = MANIFEST_FILE) -> GateResult:
    data, err = load_manifest(workflow, manifest_rel)
    if err:
        err.phase = phase
        return err
    assert data is not None
    missing: list[str] = []
    missing += require_file(workflow, data.get("project_adapter"), "project_adapter")
    for i, rel in enumerate(data.get("design_pack") or []):
        missing += require_file(workflow, rel, f"design_pack[{i}]")
    if not data.get("design_pack"):
        missing.append("design_pack: at least one design pack artifact required")
    missing += require_file(workflow, data.get("coverage"), "coverage")
    lanes = data.get("lanes") or []
    if not lanes:
        missing.append("lanes: at least one prototype lane required")
    for i, lane in enumerate(lanes):
        missing += require_file(workflow, lane.get("artifact"), f"lanes[{i}].artifact", reject_placeholder=False)
        if lane.get("notes"):
            missing += require_file(workflow, lane.get("notes"), f"lanes[{i}].notes")
    screenshots = data.get("screenshots") or []
    if not screenshots:
        missing.append("screenshots: at least one local screenshot required")
    for i, shot in enumerate(screenshots):
        missing += require_file(workflow, shot.get("path"), f"screenshots[{i}].path", reject_placeholder=False, require_image=True)

    if phase in {"before-implementation", "before-final"}:
        decision = data.get("human_decision") or {}
        if decision.get("decision") not in {"ACCEPTED", "ACCEPTED_WITH_NOTES"}:
            missing.append("human_decision: ACCEPTED or ACCEPTED_WITH_NOTES required")
        for key in ("signer", "signer_role", "decided_at", "decision_source"):
            if not str(decision.get(key) or "").strip():
                missing.append(f"human_decision.{key}: required")
        if decision.get("decision") == "ACCEPTED_WITH_NOTES" and not str(decision.get("notes_closure") or "").strip():
            missing.append("human_decision.notes_closure: required when decision is ACCEPTED_WITH_NOTES")
        missing += require_file(workflow, decision.get("artifact"), "human_decision.artifact", reject_placeholder=False)
        freeze = data.get("freeze") or {}
        missing += require_file(workflow, freeze.get("document"), "freeze.document")
        missing += require_file(workflow, freeze.get("payload"), "freeze.payload", reject_placeholder=False)
        fs = freeze.get("screenshots") or []
        if not fs:
            missing.append("freeze.screenshots: at least one frozen screenshot required")
        for i, rel in enumerate(fs):
            missing += require_file(workflow, rel, f"freeze.screenshots[{i}]", reject_placeholder=False, require_image=True)
        missing += require_file(workflow, data.get("parity_plan"), "parity_plan")

    if phase == "before-final":
        missing += require_file(workflow, data.get("parity_report"), "parity_report")
        runtime = data.get("runtime_evidence") or []
        if not runtime:
            missing.append("runtime_evidence: at least one local runtime/browser evidence required")
        for i, rel in enumerate(runtime):
            missing += require_file(workflow, rel, f"runtime_evidence[{i}]")

    if missing:
        return GateResult("BLOCKED", str(workflow), phase, missing, ["required frontend evidence manifest entries are missing or invalid"])
    return GateResult("PASS", str(workflow), phase, [], ["frontend evidence manifest phase passed"])


def print_result(result: GateResult, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"status={result.status}")
        print(f"workflow={result.workflow}")
        print(f"phase={result.phase}")
        for reason in result.reasons:
            print(f"reason={reason}")
        for item in result.missing:
            print(f"missing={item}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate frontend evidence manifest by lifecycle phase.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--manifest", default=MANIFEST_FILE)
    ap.add_argument("--phase", choices=PHASES, required=True)
    ap.add_argument("--format", choices=["json", "text"], default="json")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    workflow, workflow_err = resolve_workflow(root, args.workflow)
    if workflow_err:
        result = blocked(workflow, args.phase, workflow_err, [str(workflow)])
    elif not workflow.exists() or not workflow.is_dir():
        result = blocked(workflow, args.phase, "workflow directory does not exist", [str(workflow)])
    else:
        result = check_manifest(workflow, args.phase, args.manifest)
    print_result(result, args.format)
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
