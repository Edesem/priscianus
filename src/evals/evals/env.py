"""Read the repo's `.env` so that `make eval` finds `ANTHROPIC_API_KEY` without a manual export."""

import os
from pathlib import Path


def load_env(path: Path) -> None:
    """Set each `KEY=value` line of `path` that the environment does not already define."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)
