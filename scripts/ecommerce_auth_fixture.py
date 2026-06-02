#!/usr/bin/env python3
"""Load the local Ecommerce/Platform auth fixture for SelfCheck smoke tests.

Secrets live outside git by default: ~/.hermes/secrets/ecommerce-login.env
This helper intentionally never prints passwords or bearer tokens.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_ENV_PATH = Path("~/.hermes/secrets/ecommerce-login.env").expanduser()
SECRET_KEYS = {"password", "token", "authorization", "secret"}


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        raise SystemExit(f"auth fixture missing: {path}")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def redact(key: str, value: str) -> str:
    if any(part in key.lower() for part in SECRET_KEYS):
        return "[REDACTED]" if value else ""
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_PATH))
    parser.add_argument("--json", action="store_true", help="print redacted fixture summary as JSON")
    parser.add_argument("--shell", action="store_true", help="print shell export commands with redacted secret values for diagnostics")
    args = parser.parse_args()

    env_path = Path(args.env_file).expanduser()
    values = load_env(env_path)
    required = ["PLATFORM_DEV_ADMIN_EMAIL", "PLATFORM_DEV_ADMIN_PASSWORD", "PLATFORM_BASE_URL", "ECOMMERCE_BASE_URL"]
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise SystemExit("auth fixture missing required keys: " + ", ".join(missing))

    if args.shell:
        import shlex
        for key, value in values.items():
            print(f"export {key}={shlex.quote(redact(key, value))}")
    else:
        summary = {
            "env_file": str(env_path),
            "mode": oct(env_path.stat().st_mode & 0o777),
            "keys": {key: redact(key, value) for key, value in values.items()},
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
