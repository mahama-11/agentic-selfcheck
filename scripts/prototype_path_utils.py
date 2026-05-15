#!/usr/bin/env python3
"""Path containment helpers for prototype governance gates."""
from __future__ import annotations

from pathlib import Path


def resolve_under(root: Path, user_path: str | Path, label: str = "path") -> Path:
    """Resolve a user-supplied relative path under root, rejecting abs/../ escape."""
    root_resolved = root.resolve()
    candidate = Path(user_path)
    if candidate.is_absolute():
        raise ValueError(f"{label} must be relative to workflow directory, got absolute path: {candidate}")
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"{label} must stay inside workflow directory: {user_path}") from exc
    return resolved
