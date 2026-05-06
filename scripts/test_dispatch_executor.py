#!/usr/bin/env python3
"""Test-only SelfCheck dispatch executor.

This simulates an owner agent consuming SELFCHECK_PROMPT_FILE. It does not patch
implementation code; it exists only to verify the dispatch consume lifecycle.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

prompt = Path(os.environ["SELFCHECK_PROMPT_FILE"])
out = prompt.with_name("executor-result.json")
out.write_text(json.dumps({
    "status": "PASS",
    "owner": os.environ.get("SELFCHECK_OWNER"),
    "feature": os.environ.get("SELFCHECK_FEATURE"),
    "dispatch": os.environ.get("SELFCHECK_DISPATCH_PATH"),
    "prompt_chars": len(prompt.read_text(encoding="utf-8")),
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"TEST_EXECUTOR_PASS: {out}")
