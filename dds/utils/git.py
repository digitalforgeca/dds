"""Git info utilities."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone


def git_info() -> dict[str, str]:
    """Get current git info (hash, branch, build time)."""

    def _run(cmd: str) -> str:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else "unknown"

    return {
        "hash": _run("git rev-parse --short HEAD"),
        "branch": _run("git rev-parse --abbrev-ref HEAD"),
        "build_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
