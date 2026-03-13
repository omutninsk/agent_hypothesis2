from __future__ import annotations

import os
import re


def safe_path(filename: str) -> str | None:
    """Normalize and validate a relative path. Returns None if unsafe."""
    normalized = os.path.normpath(filename)
    if normalized.startswith("..") or normalized.startswith("/"):
        return None
    return normalized


def sanitize_skill_name(name: str) -> str | None:
    """Validate skill name: lowercase, starts with letter, only a-z0-9_."""
    if re.match(r"^[a-z][a-z0-9_]*$", name) and len(name) <= 128:
        return name
    return None
