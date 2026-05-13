#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None
try:
    import jsonschema  # type: ignore
except Exception:  # pragma: no cover
    jsonschema = None

TEMPLATE_DIR = Path('templates/frontend/project-adapter')
ADAPTER_FILE = 'PROJECT_ADAPTER.yaml'
REQUIRED_TEMPLATE_FILES = [
    'PROJECT_ADAPTER.yaml',
    'frontend-design.mdc',
    'CLAUDE_FRONTEND_SECTION.md',
    'PLAYWRIGHT_COMMANDS.md',
]
REQUIRED_COMMANDS = {'install', 'dev', 'build', 'typecheck', 'lint', 'test', 'storybook', 'playwright'}
REQUIRED_RULE_KEYS = {'cursor_rule', 'claude_frontend_section', 'command_registry'}
MANAGED_START = '<!-- agentic-selfcheck:frontend-project-adapter:start -->'
MANAGED_END = '<!-- agentic-selfcheck:frontend-project-adapter:end -->'
GENERATED_TARGETS = {
    'PROJECT_ADAPTER.yaml': ADAPTER_FILE,
    'frontend-design.mdc': '.cursor/rules/frontend-design.mdc',
    'CLAUDE_FRONTEND_SECTION.md': 'CLAUDE_FRONTEND_SECTION.md',
    'PLAYWRIGHT_COMMANDS.md': 'PLAYWRIGHT_COMMANDS.md',
}


def result(status: str, findings: list[dict[str, str]], **extra: Any) -> dict[str, Any]:
    return {'status': status, 'findings': findings, **extra}


def finding(sev: str, path: str | Path, msg: str) -> dict[str, str]:
    return {'severity': sev, 'path': str(path), 'message': msg}


def is_within(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def safe_rel(raw: str, *, field: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f'{field} must be a non-empty relative path')
    p = Path(raw.strip())
    if p.is_absolute() or '..' in p.parts:
        raise ValueError(f'{field} must not be absolute or contain path traversal')
    return p


def yaml_parse_error_message(exc: Exception) -> str:
    mark = getattr(exc, 'problem_mark', None)
    if mark is not None:
        return f'YAML parse error at line {getattr(mark, "line", 0) + 1} column {getattr(mark, "column", 0) + 1}'
    return exc.__class__.__name__


def load_yaml_file(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise ValueError('PyYAML is required to read adapter YAML')
    try:
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise ValueError(yaml_parse_error_message(exc)) from None
    if not isinstance(data, dict):
        raise ValueError('adapter config must be a YAML object')
    return data


def safe_schema_reason(err: Any) -> str:
    """Return a schema validation reason without echoing raw instance values."""
    validator = getattr(err, 'validator', '')
    if validator == 'required':
        return 'required field missing'
    if validator == 'additionalProperties':
        return 'unexpected field present'
    if validator == 'type':
        return 'invalid type'
    if validator == 'enum':
        return 'value is not one of the allowed values'
    if validator == 'const':
        return 'required constant value mismatch'
    if validator == 'pattern':
        return 'value does not match required pattern'
    if validator in {'minLength', 'maxLength', 'minimum', 'maximum', 'minItems', 'maxItems'}:
        return 'value is outside allowed bounds'
    if validator in {'oneOf', 'anyOf', 'allOf'}:
        return 'value does not match required schema alternatives'
    return 'value does not satisfy schema'


def schema_validation_errors(selfcheck_root: Path, data: dict[str, Any]) -> list[str]:
    schema_path = selfcheck_root / 'schemas/frontend-project-adapter.schema.json'
    try:
        schema = json.loads(schema_path.read_text(encoding='utf-8'))
    except Exception as exc:
        return [f'adapter schema invalid JSON: {exc.__class__.__name__}']
    if jsonschema is None:
        return ['jsonschema is required to validate adapter config']
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        path = '.'.join(str(p) for p in err.path) or '<root>'
        errors.append(f'{path}: {safe_schema_reason(err)}')
    return errors


def validate_parent_paths(project_root: Path, rel: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    cur = project_root
    for part in rel.parts[:-1]:
        cur = cur / part
        if cur.exists() and not cur.is_dir():
            findings.append(finding('error', cur, 'target parent path exists and is not a directory'))
            break
    return findings


def remember_backup(dest: Path, project_root: Path, backups: dict[Path, bytes | None]) -> None:
    rel = dest.relative_to(project_root)
    if rel not in backups:
        backups[rel] = dest.read_bytes() if dest.exists() and dest.is_file() else None


def rollback(project_root: Path, backups: dict[Path, bytes | None]) -> None:
    for rel, content in reversed(list(backups.items())):
        dest = project_root / rel
        if content is None:
            if dest.exists() and dest.is_file():
                dest.unlink()
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
    for rel in sorted(backups, key=lambda p: len(p.parts), reverse=True):
        parent = (project_root / rel).parent
        while parent != project_root and is_within(parent, project_root):
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


def dump_template(src: Path, dest: Path, force: bool, project_root: Path, written: list[str], skipped: list[str], findings: list[dict[str, str]], backups: dict[Path, bytes | None]) -> None:
    resolved = dest.resolve()
    if not is_within(resolved, project_root):
        findings.append(finding('error', dest, 'target path escapes project root'))
        return
    if dest.exists() and not force:
        findings.append(finding('error', dest, 'target exists; refusing to overwrite without --force'))
        return
    remember_backup(dest, project_root, backups)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    written.append(str(dest.relative_to(project_root)))


def upsert_claude_section(template: Path, project_root: Path, force: bool, written: list[str], findings: list[dict[str, str]], backups: dict[Path, bytes | None]) -> None:
    claude = project_root / 'CLAUDE.md'
    section = template.read_text(encoding='utf-8').strip() + '\n'
    if claude.exists() and not force:
        findings.append(finding('error', claude, 'CLAUDE.md exists; refusing to modify human-authored file without --force'))
        return
    if claude.exists():
        text = claude.read_text(encoding='utf-8')
        if MANAGED_START in text and MANAGED_END in text:
            before, rest = text.split(MANAGED_START, 1)
            _, after = rest.split(MANAGED_END, 1)
            text = before.rstrip() + '\n\n' + section + after.lstrip()
        else:
            text = text.rstrip() + '\n\n' + section
    else:
        text = '# Claude Project Instructions\n\n' + section
    remember_backup(claude, project_root, backups)
    claude.write_text(text, encoding='utf-8')
    written.append('CLAUDE.md')


def validate_config(project_root: Path, selfcheck_root: Path | None = None) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    cfg_path = project_root / ADAPTER_FILE
    if not cfg_path.exists():
        return [finding('error', cfg_path, 'PROJECT_ADAPTER.yaml is missing')]
    try:
        data = load_yaml_file(cfg_path)
    except Exception as exc:
        return [finding('error', cfg_path, f'malformed adapter config: {exc}')]
    if selfcheck_root is not None:
        for err in schema_validation_errors(selfcheck_root, data):
            findings.append(finding('error', cfg_path, 'schema violation: ' + err))
    allowed_top = {'schema_version', 'project', 'frontend_adapter'}
    extra = set(data) - allowed_top
    missing = allowed_top - set(data)
    if extra:
        findings.append(finding('error', cfg_path, 'unexpected top-level fields: ' + ', '.join(sorted(extra))))
    if missing:
        findings.append(finding('error', cfg_path, 'missing required fields: ' + ', '.join(sorted(missing))))
    adapter = data.get('frontend_adapter')
    if not isinstance(adapter, dict):
        findings.append(finding('error', cfg_path, 'frontend_adapter must be an object'))
        return findings
    for key in ['rule_files', 'commands', 'evidence_paths', 'policies']:
        if key not in adapter:
            findings.append(finding('error', cfg_path, f'frontend_adapter.{key} is required'))
    rule_files = adapter.get('rule_files', {})
    if not isinstance(rule_files, dict):
        findings.append(finding('error', cfg_path, 'frontend_adapter.rule_files must be an object'))
        rule_files = {}
    missing_rules = REQUIRED_RULE_KEYS - set(rule_files)
    if missing_rules:
        findings.append(finding('error', cfg_path, 'missing required rule files: ' + ', '.join(sorted(missing_rules))))
    for key, raw in rule_files.items():
        try:
            rel = safe_rel(raw, field=f'rule_files.{key}')
        except ValueError as exc:
            findings.append(finding('error', cfg_path, str(exc)))
            continue
        p = project_root / rel
        if not is_within(p, project_root):
            findings.append(finding('error', p, f'rule file {key} escapes project root'))
        elif not p.exists() or not p.is_file() or p.stat().st_size < 40:
            findings.append(finding('error', p, f'required rule file {key} is missing or too small'))
    commands = adapter.get('commands', {})
    if not isinstance(commands, dict):
        findings.append(finding('error', cfg_path, 'frontend_adapter.commands must be an object'))
        commands = {}
    missing_commands = REQUIRED_COMMANDS - set(commands)
    if missing_commands:
        findings.append(finding('error', cfg_path, 'missing required commands: ' + ', '.join(sorted(missing_commands))))
    for key, value in commands.items():
        if key not in REQUIRED_COMMANDS:
            findings.append(finding('error', cfg_path, f'unexpected command key: {key}'))
        if not isinstance(value, str) or not value.strip() or value.strip().lower() in {'todo', 'tbd', 'none'}:
            findings.append(finding('error', cfg_path, f'command {key} must be a concrete non-empty command string'))
    evidence_paths = adapter.get('evidence_paths', [])
    if not isinstance(evidence_paths, list) or not evidence_paths:
        findings.append(finding('error', cfg_path, 'frontend_adapter.evidence_paths must be a non-empty array'))
    else:
        for i, raw in enumerate(evidence_paths):
            try:
                rel = safe_rel(raw, field=f'evidence_paths[{i}]')
            except ValueError as exc:
                findings.append(finding('error', cfg_path, str(exc)))
                continue
            if not is_within(project_root / rel, project_root):
                findings.append(finding('error', cfg_path, f'evidence path {i} escapes project root'))
    return findings


def preflight_init(selfcheck_root: Path, project_root: Path, force: bool) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    template_root = selfcheck_root / TEMPLATE_DIR
    for name in REQUIRED_TEMPLATE_FILES:
        p = template_root / name
        if not p.exists() or p.stat().st_size < 80:
            findings.append(finding('error', p, 'required adapter template missing or empty'))
    for target_rel in GENERATED_TARGETS.values():
        try:
            rel = safe_rel(target_rel, field=f'target.{target_rel}')
        except ValueError as exc:
            findings.append(finding('error', target_rel, str(exc)))
            continue
        dest = project_root / rel
        if not is_within(dest, project_root):
            findings.append(finding('error', dest, 'target path escapes project root'))
        else:
            findings.extend(validate_parent_paths(project_root, rel))
            if dest.exists() and not force:
                findings.append(finding('error', dest, 'target exists; refusing to overwrite without --force'))
    claude = project_root / 'CLAUDE.md'
    findings.extend(validate_parent_paths(project_root, Path('CLAUDE.md')))
    if claude.exists() and not force:
        findings.append(finding('error', claude, 'CLAUDE.md exists; refusing to modify human-authored file without --force'))
    template_cfg = template_root / ADAPTER_FILE
    if template_cfg.exists():
        try:
            template_data = load_yaml_file(template_cfg)
            for err in schema_validation_errors(selfcheck_root, template_data):
                findings.append(finding('error', template_cfg, 'template schema violation: ' + err))
            adapter = template_data.get('frontend_adapter', {}) if isinstance(template_data, dict) else {}
            commands = adapter.get('commands', {}) if isinstance(adapter, dict) else {}
            if isinstance(commands, dict):
                for key, value in commands.items():
                    if not isinstance(value, str) or not value.strip() or value.strip().lower() in {'todo', 'tbd', 'none'}:
                        findings.append(finding('error', template_cfg, f'template command {key} must be concrete'))
        except Exception as exc:
            findings.append(finding('error', template_cfg, f'template adapter config malformed: {exc}'))
    return findings


def init_adapter(selfcheck_root: Path, project_root: Path, force: bool) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    if not project_root.exists():
        project_root.mkdir(parents=True)
    if not project_root.is_dir():
        return result('FAIL', [finding('error', project_root, 'project root is not a directory')])
    findings = preflight_init(selfcheck_root, project_root, force)
    if findings:
        return result('FAIL', findings, written=[], skipped=[], project_root=str(project_root))
    template_root = selfcheck_root / TEMPLATE_DIR
    written: list[str] = []
    skipped: list[str] = []
    backups: dict[Path, bytes | None] = {}
    try:
        for src_name, target_rel in GENERATED_TARGETS.items():
            dump_template(template_root / src_name, project_root / target_rel, force, project_root, written, skipped, findings, backups)
        upsert_claude_section(template_root / 'CLAUDE_FRONTEND_SECTION.md', project_root, force, written, findings, backups)
        if not findings:
            findings.extend(validate_config(project_root, selfcheck_root))
        if findings:
            rollback(project_root, backups)
            written = []
    except Exception as exc:
        rollback(project_root, backups)
        return result('FAIL', [finding('error', project_root, f'initialization failed: {exc.__class__.__name__}')], written=[], skipped=skipped, project_root=str(project_root))
    return result('PASS' if not findings else 'FAIL', findings, written=written, skipped=skipped, project_root=str(project_root))


def check_base(selfcheck_root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    template_root = selfcheck_root / TEMPLATE_DIR
    for name in REQUIRED_TEMPLATE_FILES:
        p = template_root / name
        if not p.exists() or p.stat().st_size < 80:
            findings.append(finding('error', p, 'required adapter template missing or empty'))
    schema = selfcheck_root / 'schemas/frontend-project-adapter.schema.json'
    if not schema.exists() or schema.stat().st_size < 100:
        findings.append(finding('error', schema, 'adapter schema missing or empty'))
    else:
        try:
            json.loads(schema.read_text(encoding='utf-8'))
        except Exception as exc:
            findings.append(finding('error', schema, f'adapter schema invalid JSON: {exc}'))
    return result('PASS' if not findings else 'FAIL', findings)


def main() -> int:
    ap = argparse.ArgumentParser(description='Initialize or validate generic frontend project adapter rules.')
    ap.add_argument('--root', default='.', help='agentic-selfcheck repository root containing templates/schemas')
    ap.add_argument('--project-root', default=None, help='frontend project root to initialize or validate')
    ap.add_argument('--force', action='store_true', help='allow replacement/managed insertion for existing generated targets')
    ap.add_argument('--check', action='store_true', help='validate an existing project adapter instead of initializing')
    ap.add_argument('--base-check', action='store_true', help='validate repository adapter templates/schema only')
    ap.add_argument('--format', choices=['json', 'text'], default='json')
    args = ap.parse_args()
    selfcheck_root = Path(args.root).resolve()
    try:
        if args.base_check:
            out = check_base(selfcheck_root)
        else:
            project_root = Path(args.project_root or args.root).resolve()
            if args.check:
                findings = validate_config(project_root, selfcheck_root)
                out = result('PASS' if not findings else 'FAIL', findings, project_root=str(project_root))
            else:
                out = init_adapter(selfcheck_root, project_root, args.force)
    except Exception as exc:
        out = result('FAIL', [finding('error', args.project_root or args.root, f'unhandled failure: {exc.__class__.__name__}')])
    if args.format == 'json':
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print('status=' + out['status'])
        for f in out['findings']:
            print(f"{f['severity']}: {f['path']}: {f['message']}")
    return 0 if out['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
