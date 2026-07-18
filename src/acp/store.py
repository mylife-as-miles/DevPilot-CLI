"""Small durable index for ACP sessions; run artifacts remain project-owned."""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .._app import GLOBAL_CONFIG_DIR
from .runtime import AcpSession


class AcpSessionStore:
    def __init__(self, root: Path | None = None) -> None:
        configured_root = os.environ.get("DEVPILOT_ACP_SESSION_DIR", "").strip()
        self.root = (
            root
            or (Path(configured_root) if configured_root else GLOBAL_CONFIG_DIR / "acp_sessions")
        ).expanduser().resolve()

    def save(self, session: AcpSession) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        session.updated_at = datetime.now(timezone.utc).isoformat()
        payload = {
            key: value
            for key, value in asdict(session).items()
            if key != "process"
        }
        payload["cwd"] = str(session.cwd)
        target = self.root / f"{session.session_id}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, target)

    def load(self, session_id: str) -> AcpSession | None:
        safe_id = self._safe_session_id(session_id)
        target = self.root / f"{safe_id}.json"
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        try:
            return AcpSession(
                session_id=str(payload["session_id"]),
                cwd=Path(payload["cwd"]),
                mode=str(payload.get("mode") or "research"),
                model=payload.get("model"),
                reasoning_effort=payload.get("reasoning_effort"),
                run_name=str(payload.get("run_name") or ""),
                has_started=bool(payload.get("has_started", False)),
                title=payload.get("title"),
                updated_at=payload.get("updated_at"),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def list(self, cwd: str | None = None) -> Iterable[AcpSession]:
        if not self.root.is_dir():
            return ()
        cwd_path = Path(cwd).expanduser().resolve() if cwd else None
        sessions: list[AcpSession] = []
        for target in self.root.glob("*.json"):
            session = self.load(target.stem)
            if session and (cwd_path is None or session.cwd == cwd_path):
                sessions.append(session)
        sessions.sort(key=lambda item: item.updated_at or "", reverse=True)
        return tuple(sessions)

    @staticmethod
    def _safe_session_id(session_id: str) -> str:
        if not session_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in session_id):
            raise ValueError("invalid ACP session id")
        return session_id
