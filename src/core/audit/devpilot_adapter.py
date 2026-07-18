"""Scaffold for adapting DevPilot runtime objects to iFixAi concepts.

Phase 1 intentionally keeps the audit integration CLI-only.  This adapter marks
the future boundary for evaluating DevPilot agents directly without mixing
iFixAi internals into DevPilot's runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DevPilotAuditAdapter:
    """Minimal placeholder adapter for future native agent audits."""

    project_name: str = "DevPilot"
    metadata: dict[str, Any] = field(default_factory=dict)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return tool metadata available to the audited agent."""

        return []

    def get_audit_trail(self) -> list[dict[str, Any]]:
        """Return structured events for future iFixAi-style inspections."""

        return []

    def send_message(self, message: str) -> str:
        """Future hook for asking a DevPilot agent under test."""

        raise NotImplementedError("DevPilot agent audit execution is not implemented in Phase 1.")

    def authorize_tool(self, tool_name: str, arguments: dict[str, Any]) -> bool:
        """Future hook for deterministic tool authorization during audits."""

        raise NotImplementedError("Tool authorization auditing is not implemented in Phase 1.")

    def retrieve_sources(self, query: str) -> list[dict[str, Any]]:
        """Future hook for evidence retrieval during audits."""

        raise NotImplementedError("Source retrieval auditing is not implemented in Phase 1.")
