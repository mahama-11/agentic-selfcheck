#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(root: Path, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ['python3', 'scripts/frontend_project_adapter_init.py', '--root', '.', '--project-root', str(project), *args, '--format', 'json'],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def load_out(cp: subprocess.CompletedProcess[str]) -> dict:
    try:
        return json.loads(cp.stdout)
    except Exception:
        return {'status': 'UNPARSEABLE', 'stdout': cp.stdout, 'stderr': cp.stderr}


def write_good_project(root: Path, project: Path) -> None:
    cp = run(root, project)
    if cp.returncode != 0:
        raise RuntimeError(cp.stdout + cp.stderr)


def copy_selfcheck_root(src: Path, dest: Path) -> None:
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns('.git', '.hermes', '__pycache__', '.pytest_cache'),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--format', choices=['json', 'text'], default='json')
    args = ap.parse_args()
    root = Path(args.root).resolve()
    cases = []
    ok = True

    # Base repository templates/schema check.
    base = subprocess.run(
        ['python3', 'scripts/frontend_project_adapter_init.py', '--root', '.', '--base-check', '--format', 'json'],
        cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    passed = base.returncode == 0
    ok = ok and passed
    cases.append({'case': 'base-check', 'expected': 'PASS', 'actual': 'PASS' if passed else 'FAIL', 'returncode': base.returncode, 'stdout': base.stdout[-1600:], 'stderr': base.stderr[-1600:]})

    with tempfile.TemporaryDirectory(prefix='frontend-adapter-smoke-') as tmp:
        tmp_root = Path(tmp)

        # Positive init + check.
        project = tmp_root / 'good-project'
        cp = run(root, project)
        passed = cp.returncode == 0
        ok = ok and passed
        cases.append({'case': 'good-init', 'expected': 'PASS', 'actual': 'PASS' if passed else 'FAIL', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})
        cp_check = run(root, project, '--check')
        passed = cp_check.returncode == 0
        ok = ok and passed
        cases.append({'case': 'good-check', 'expected': 'PASS', 'actual': 'PASS' if passed else 'FAIL', 'returncode': cp_check.returncode, 'stdout': cp_check.stdout[-2200:], 'stderr': cp_check.stderr[-1000:]})

        # Refuse overwrite without --force and leave no partial files.
        conflict_project = tmp_root / 'conflict-project'
        conflict_project.mkdir()
        (conflict_project / 'PLAYWRIGHT_COMMANDS.md').write_text('# human authored command registry\n\nDo not overwrite this content.\n', encoding='utf-8')
        cp = run(root, conflict_project)
        partial_targets = [
            conflict_project / 'PROJECT_ADAPTER.yaml',
            conflict_project / '.cursor/rules/frontend-design.mdc',
            conflict_project / 'CLAUDE_FRONTEND_SECTION.md',
            conflict_project / 'CLAUDE.md',
        ]
        passed = cp.returncode != 0 and 'refusing to overwrite without --force' in cp.stdout and not any(p.exists() for p in partial_targets)
        passed = passed and 'human authored command registry' in (conflict_project / 'PLAYWRIGHT_COMMANDS.md').read_text(encoding='utf-8')
        ok = ok and passed
        cases.append({'case': 'bad-overwrite-without-force', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        # Parent path conflict (.cursor as a regular file) fails before writing anything.
        parent_conflict = tmp_root / 'parent-conflict'
        parent_conflict.mkdir()
        (parent_conflict / '.cursor').write_text('not a directory\n', encoding='utf-8')
        cp = run(root, parent_conflict)
        partial_targets = [
            parent_conflict / 'PROJECT_ADAPTER.yaml',
            parent_conflict / '.cursor/rules/frontend-design.mdc',
            parent_conflict / 'CLAUDE_FRONTEND_SECTION.md',
            parent_conflict / 'PLAYWRIGHT_COMMANDS.md',
            parent_conflict / 'CLAUDE.md',
        ]
        passed = cp.returncode != 0 and 'target parent path exists and is not a directory' in cp.stdout and not any(p.exists() for p in partial_targets if p != parent_conflict / '.cursor')
        passed = passed and (parent_conflict / '.cursor').is_file()
        ok = ok and passed
        cases.append({'case': 'bad-parent-path-conflict-no-partial-writes', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        # --force replaces managed/generated targets and remains valid.
        cp = run(root, conflict_project, '--force')
        passed = cp.returncode == 0 and 'human authored command registry' not in (conflict_project / 'PLAYWRIGHT_COMMANDS.md').read_text(encoding='utf-8')
        ok = ok and passed
        cases.append({'case': 'good-force-replaces-generated-targets', 'expected': 'PASS', 'actual': 'PASS' if passed else 'FAIL', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        # Existing CLAUDE.md must fail without force, then append/replace managed section with force.
        claude_project = tmp_root / 'claude-existing'
        claude_project.mkdir()
        (claude_project / 'CLAUDE.md').write_text('# Human Claude\n\nExisting human instructions.\n', encoding='utf-8')
        cp = run(root, claude_project)
        no_partial = not (claude_project / 'PROJECT_ADAPTER.yaml').exists() and not (claude_project / '.cursor/rules/frontend-design.mdc').exists() and not (claude_project / 'CLAUDE_FRONTEND_SECTION.md').exists() and not (claude_project / 'PLAYWRIGHT_COMMANDS.md').exists()
        passed = cp.returncode != 0 and 'CLAUDE.md exists' in cp.stdout and no_partial
        ok = ok and passed
        cases.append({'case': 'bad-existing-claude-without-force', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})
        cp = run(root, claude_project, '--force')
        text = (claude_project / 'CLAUDE.md').read_text(encoding='utf-8')
        passed = cp.returncode == 0 and 'Existing human instructions.' in text and 'agentic-selfcheck:frontend-project-adapter:start' in text
        ok = ok and passed
        cases.append({'case': 'good-force-claude-managed-section', 'expected': 'PASS', 'actual': 'PASS' if passed else 'FAIL', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        # Malformed adapter config fails closed without echoing secret-like source text.
        malformed = tmp_root / 'malformed'
        write_good_project(root, malformed)
        fake_secret = 'sk-abcdefghijklmnopqrstuvwxyz1234567890'
        (malformed / 'PROJECT_ADAPTER.yaml').write_text(f'schema_version: [unterminated\napi_key: {fake_secret}\n', encoding='utf-8')
        cp = run(root, malformed, '--check')
        passed = cp.returncode != 0 and 'malformed adapter config' in cp.stdout and fake_secret not in cp.stdout and 'api_key' not in cp.stdout
        ok = ok and passed
        cases.append({'case': 'bad-malformed-config-redacted', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        # Schema violations fail closed without leaking raw instance values.
        bad_schema = tmp_root / 'bad-schema-version'
        write_good_project(root, bad_schema)
        text = (bad_schema / 'PROJECT_ADAPTER.yaml').read_text(encoding='utf-8').replace("schema_version: '1.0'", "schema_version: '2.0'")
        (bad_schema / 'PROJECT_ADAPTER.yaml').write_text(text, encoding='utf-8')
        cp = run(root, bad_schema, '--check')
        passed = cp.returncode != 0 and 'schema violation' in cp.stdout and 'required constant value mismatch' in cp.stdout and "'2.0'" not in cp.stdout
        ok = ok and passed
        cases.append({'case': 'bad-schema-version', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        secret_path_schema = tmp_root / 'bad-secret-absolute-path'
        write_good_project(root, secret_path_schema)
        secret_abs = '/tmp/sk-secret-token-source/Bearer-api_key-password'
        text = (secret_path_schema / 'PROJECT_ADAPTER.yaml').read_text(encoding='utf-8').replace('    - test-results', f'    - {secret_abs}')
        (secret_path_schema / 'PROJECT_ADAPTER.yaml').write_text(text, encoding='utf-8')
        cp = run(root, secret_path_schema, '--check')
        leaked = any(token in cp.stdout for token in [secret_abs, 'sk-secret-token-source', 'Bearer-api_key-password'])
        passed = cp.returncode != 0 and 'schema violation' in cp.stdout and 'value does not match required pattern' in cp.stdout and not leaked
        ok = ok and passed
        cases.append({'case': 'bad-schema-secret-absolute-path-redacted', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        bad_policy = tmp_root / 'bad-policy'
        write_good_project(root, bad_policy)
        text = (bad_policy / 'PROJECT_ADAPTER.yaml').read_text(encoding='utf-8').replace('    no_overwrite_without_force: true', '    no_overwrite_without_force: false')
        (bad_policy / 'PROJECT_ADAPTER.yaml').write_text(text, encoding='utf-8')
        cp = run(root, bad_policy, '--check')
        passed = cp.returncode != 0 and 'schema violation' in cp.stdout and 'required constant value mismatch' in cp.stdout and 'False was expected' not in cp.stdout
        ok = ok and passed
        cases.append({'case': 'bad-required-policy-value', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        # Corrupt copied template must fail preflight before writing project files; source checkout remains unchanged.
        corrupt_template_project = tmp_root / 'corrupt-template-project'
        source_template = root / 'templates/frontend/project-adapter/PROJECT_ADAPTER.yaml'
        source_template_before = source_template.read_text(encoding='utf-8')
        corrupt_root = tmp_root / 'selfcheck-corrupt-template-copy'
        copy_selfcheck_root(root, corrupt_root)
        template = corrupt_root / 'templates/frontend/project-adapter/PROJECT_ADAPTER.yaml'
        template.write_text(template.read_text(encoding='utf-8').replace("schema_version: '1.0'", "schema_version: '2.0'"), encoding='utf-8')
        cp = run(corrupt_root, corrupt_template_project)
        source_template_after = source_template.read_text(encoding='utf-8')
        partial_targets = [
            corrupt_template_project / 'PROJECT_ADAPTER.yaml',
            corrupt_template_project / '.cursor/rules/frontend-design.mdc',
            corrupt_template_project / 'CLAUDE_FRONTEND_SECTION.md',
            corrupt_template_project / 'PLAYWRIGHT_COMMANDS.md',
            corrupt_template_project / 'CLAUDE.md',
        ]
        passed = cp.returncode != 0 and 'template schema violation' in cp.stdout and not any(p.exists() for p in partial_targets) and source_template_before == source_template_after
        ok = ok and passed
        cases.append({'case': 'bad-corrupt-template-no-source-mutation-no-partial-writes', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        # Missing required commands fails closed.
        missing_cmd = tmp_root / 'missing-command'
        write_good_project(root, missing_cmd)
        text = (missing_cmd / 'PROJECT_ADAPTER.yaml').read_text(encoding='utf-8').replace('    playwright: npx playwright test\n', '')
        (missing_cmd / 'PROJECT_ADAPTER.yaml').write_text(text, encoding='utf-8')
        cp = run(root, missing_cmd, '--check')
        passed = cp.returncode != 0 and 'missing required commands' in cp.stdout
        ok = ok and passed
        cases.append({'case': 'bad-missing-required-command', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        # Missing required rules fails closed.
        missing_rule = tmp_root / 'missing-rule'
        write_good_project(root, missing_rule)
        (missing_rule / '.cursor/rules/frontend-design.mdc').unlink()
        cp = run(root, missing_rule, '--check')
        passed = cp.returncode != 0 and 'required rule file cursor_rule is missing' in cp.stdout
        ok = ok and passed
        cases.append({'case': 'bad-missing-required-rule-file', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

        # Path traversal fails closed.
        traversal = tmp_root / 'path-traversal'
        write_good_project(root, traversal)
        text = (traversal / 'PROJECT_ADAPTER.yaml').read_text(encoding='utf-8').replace('    command_registry: PLAYWRIGHT_COMMANDS.md', '    command_registry: ../PLAYWRIGHT_COMMANDS.md')
        (traversal / 'PROJECT_ADAPTER.yaml').write_text(text, encoding='utf-8')
        cp = run(root, traversal, '--check')
        passed = cp.returncode != 0 and 'path traversal' in cp.stdout
        ok = ok and passed
        cases.append({'case': 'bad-path-traversal', 'expected': 'FAIL', 'actual': 'FAIL' if passed else 'PASS', 'returncode': cp.returncode, 'stdout': cp.stdout[-2200:], 'stderr': cp.stderr[-1000:]})

    result = {'status': 'PASS' if ok else 'FAIL', 'cases': cases}
    if args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print('status=' + result['status'])
        for case in cases:
            print(f"{case['case']}: expected {case['expected']} actual {case['actual']}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
