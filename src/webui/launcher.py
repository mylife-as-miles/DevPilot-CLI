"""Launch helper for the read-only WebUI.

Centralizes the "pick a port and bind" logic so the CLI can offer a zero-config
default (try 8765, roll forward if it's taken) while staying easy to unit-test
without standing up a real run.
"""

from __future__ import annotations

import logging
from typing import Any

from .server import WebUIServer

log = logging.getLogger(__name__)


def start_webui(
    run_state: Any,
    bus: Any,
    *,
    preferred: int,
    enabled: bool = True,
    auto: bool = False,
    scan: int = 1,
    companion: Any | None = None,
    enable_input: bool = False,
) -> WebUIServer | None:
    """Start a ``WebUIServer`` and return it, or ``None`` if disabled/no port.

    - ``enabled=False`` → returns ``None`` immediately (opt-out).
    - tries ``preferred`` first; when ``auto`` is set, walks up to ``scan`` ports
      (``preferred`` … ``preferred+scan-1``) until one binds, so a busy 8765
      silently rolls to 8766. ``WebUIServer.start()`` returns False on bind
      failure rather than raising, which makes the scan a simple loop.
    - explicit (non-auto) ports try exactly once: a taken port is surfaced as
      ``None`` rather than silently moved.
    - ``enable_input`` + ``companion`` make the browser interactive (ask / steer
      / answer gates), behind a per-run token. Default is read-only.
    """
    if not enabled or preferred is None:
        return None
    span = max(1, scan) if auto else 1
    for port in range(preferred, preferred + span):
        server = WebUIServer(run_state, bus, port=port,
                             companion=companion, enable_input=enable_input)
        if server.start():
            return server
    log.warning("WebUI could not bind any port in %d..%d", preferred, preferred + span - 1)
    return None
