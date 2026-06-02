#!/usr/bin/env python3
"""Regression tests for SelfCheck control-plane engineering invariants."""
from __future__ import annotations

import json
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from selfcheck.__main__ import audit, load_index, run_verifier


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def minimal_root() -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name) / "selfcheck"
    project_root = Path(tmp.name) / "project"
    root.mkdir()
    project_root.mkdir()
    # Reuse schemas from this checkout so the fixture stays focused on behavior.
    source = Path(__file__).resolve().parents[1]
    for folder in ["schemas"]:
        for src in (source / folder).glob("*.json"):
            write(root / folder / src.name, src.read_text(encoding="utf-8"))
    write(root / "capabilities" / "cap.yaml", """
    id: cap
    description: test capability
    contracts:
      - fixture contract
    verifiers: []
    """)
    write(root / "repair-policies" / "default-repair-policy.yaml", """
    id: default-repair-policy
    max_attempts: 2
    same_failure_limit: 2
    owners:
      evidence: orchestrator
      static: developer
    review_after_fix: []
    terminal_statuses: [PASS, PASS_WITH_NOTES, BLOCKED, ESCALATE]
    escalation: []
    """)
    write(root / "projects" / "proj.yaml", f"""
    id: proj
    description: project fixture
    root: {project_root}
    services: {{}}
    """)
    write(root / "verifiers" / "note-verifier.yaml", """
    id: note-verifier
    kind: static
    description: emits PASS_WITH_NOTES
    command: scripts/note_verifier.py
    """)
    write(root / "features" / "feat.yaml", """
    id: feat
    project: proj
    description: feature fixture
    level_target: L3
    repair_policy: default-repair-policy
    depends_on: [cap]
    must_pass:
      static: [note-verifier]
    reviewer_gates: [final-verification]
    human_required: [human boundary]
    evidence_required:
      - .hermes/workflows/feat/01-requirement.md
    """)
    write(root / "scripts" / "note_verifier.py", """
    #!/usr/bin/env python3
    import json
    print(json.dumps({"status":"PASS_WITH_NOTES","note":"coverage limitation"}))
    """)
    (root / "scripts" / "note_verifier.py").chmod(0o755)
    return tmp, root, project_root


def test_audit_resolves_relative_evidence_against_feature_project_root() -> None:
    tmp, root, project_root = minimal_root()
    try:
        # Evidence exists in the SelfCheck checkout but not in the project. It must not satisfy
        # a project feature contract.
        write(root / ".hermes/workflows/feat/01-requirement.md", "wrong root evidence\n")
        issues = audit(root, "feat", strict_missing=True)
        assert any(i.level == "ERROR" and str(project_root) in i.path for i in issues), issues

        write(project_root / ".hermes/workflows/feat/01-requirement.md", "project evidence\n")
        issues = audit(root, "feat", strict_missing=True)
        assert not any(i.level == "ERROR" and "missing required evidence" in i.message for i in issues), issues
    finally:
        tmp.cleanup()


def test_verifier_pass_with_notes_is_preserved_from_json_stdout() -> None:
    tmp, root, project_root = minimal_root()
    try:
        feature = load_index(root, "feature")["feat"]
        verifier = load_index(root, "verifier")["note-verifier"]
        report = run_verifier(root, feature, verifier, timeout=10)
        assert report["status"] == "PASS_WITH_NOTES", report
    finally:
        tmp.cleanup()


if __name__ == "__main__":
    test_audit_resolves_relative_evidence_against_feature_project_root()
    test_verifier_pass_with_notes_is_preserved_from_json_stdout()
    print("PASS: selfcheck engineering regression tests")
