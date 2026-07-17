"""Safe subprocess helpers — always shell=False, always with timeout."""

from __future__ import annotations

import shutil
import subprocess
from typing import Sequence


_DEFAULT_TIMEOUT = 30  # seconds


def run_safe(
    cmd: Sequence[str],
    *,
    timeout: int = _DEFAULT_TIMEOUT,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run *cmd* with ``shell=False`` and a wall-clock timeout.

    Returns a ``CompletedProcess`` with text stdout/stderr.
    Raises ``FileNotFoundError`` if the executable is missing,
    ``subprocess.TimeoutExpired`` on timeout, or
    ``subprocess.CalledProcessError`` on non-zero exit.
    """
    return subprocess.run(
        list(cmd),
        shell=False,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def which(name: str) -> str | None:
    """Thin wrapper around :func:`shutil.which`."""
    return shutil.which(name)


def is_available(name: str) -> bool:
    """Return True if *name* is found on PATH."""
    return which(name) is not None
