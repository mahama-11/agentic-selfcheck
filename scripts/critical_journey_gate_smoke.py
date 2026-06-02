#!/usr/bin/env python3
"""Smoke tests for the generic critical journey gate."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def fixture_root() -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
    tmp = tempfile.TemporaryDirectory()
    root = Path(tmp.name) / "selfcheck"
    project = Path(tmp.name) / "project"
    root.mkdir()
    project.mkdir()
    shutil.copytree(ROOT / "schemas", root / "schemas")
    write(root / "projects" / "demo-project.yaml", f"""
    id: demo-project
    description: demo project
    root: {project}
    services: {{}}
    """)
    write(root / "journeys" / "demo-critical-journey.yaml", """
    id: demo-critical-journey
    project: demo-project
    description: Demo critical journey.
    phases: [api]
    adapter:
      command: scripts/adapters/demo_adapter.py
    secret_fixture:
      path: .secrets/demo.env
      required: true
      required_keys: [DEMO_EMAIL, DEMO_PASSWORD]
    report_aliases:
      - project
    """)
    write(project / ".secrets" / "demo.env", """
    DEMO_EMAIL=demo@example.com
    DEMO_PASSWORD=topsecret
    """)
    write(root / "scripts" / "adapters" / "demo_adapter.py", """
    #!/usr/bin/env python3
    import json, os
    print(json.dumps({
      "status": "PASS",
      "phase": os.environ.get("SELFCHECK_JOURNEY_PHASE"),
      "project_root": os.environ.get("SELFCHECK_PROJECT_ROOT"),
      "auth_fixture": os.environ.get("SELFCHECK_AUTH_FIXTURE"),
      "password": os.environ.get("DEMO_PASSWORD"),
    }))
    """)
    (root / "scripts" / "adapters" / "demo_adapter.py").chmod(0o755)
    return tmp, root, project


def run_gate(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "critical_journey_gate.py"), "--root", str(root), *args],
        text=True,
        capture_output=True,
        timeout=20,
    )


def test_journey_runner_writes_redacted_reports_under_project_root() -> None:
    tmp, root, project = fixture_root()
    try:
        proc = run_gate(root, "--journey", "demo-critical-journey", "--phase", "api")
        assert proc.returncode == 0, proc.stderr + proc.stdout
        report = json.loads((root / "reports/critical-journeys/demo-critical-journey/api.json").read_text())
        project_report = json.loads((project / "reports/critical-journeys/demo-critical-journey/api.json").read_text())
        assert report["status"] == "PASS", report
        assert report["project_root"] == str(project.resolve()), report
        serialized = json.dumps(report, ensure_ascii=False)
        assert "topsecret" not in serialized, serialized
        assert project_report["status"] == "PASS", project_report
    finally:
        tmp.cleanup()


def test_journey_runner_rejects_unsafe_adapter_command() -> None:
    tmp, root, _ = fixture_root()
    try:
        text = (root / "journeys/demo-critical-journey.yaml").read_text()
        (root / "journeys/demo-critical-journey.yaml").write_text(text.replace("scripts/adapters/demo_adapter.py", "/bin/echo"))
        proc = run_gate(root, "--journey", "demo-critical-journey", "--phase", "api")
        assert proc.returncode != 0, proc.stdout
        assert "unsafe adapter command" in (proc.stderr + proc.stdout)
        assert "Traceback" not in (proc.stderr + proc.stdout)
    finally:
        tmp.cleanup()


if __name__ == "__main__":
    test_journey_runner_writes_redacted_reports_under_project_root()
    test_journey_runner_rejects_unsafe_adapter_command()
    print("PASS: critical journey gate smoke")
