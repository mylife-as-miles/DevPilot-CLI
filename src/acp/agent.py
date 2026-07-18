"""Official Agent Client Protocol SDK adapter for DevPilot."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any
from uuid import uuid4

from acp import (
    Agent,
    InitializeResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
    run_agent,
    text_block,
    update_agent_message,
)
from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    ClientCapabilities,
    CloseSessionResponse,
    Implementation,
    ListSessionsResponse,
    McpCapabilities,
    PromptCapabilities,
    ResumeSessionResponse,
    SessionCapabilities,
    SessionCloseCapabilities,
    SessionConfigOptionSelect,
    SessionConfigSelectOption,
    SessionInfo,
    SessionListCapabilities,
    SessionMode,
    SessionModeState,
    SessionResumeCapabilities,
    SetSessionConfigOptionResponse,
    SetSessionModeResponse,
)

from .runtime import AcpSession, DEVPILOT_MODES, MODE_IDS, build_run_invocation, extract_prompt_text
from .store import AcpSessionStore


def _runtime_version() -> str:
    for distribution in ("miles-devpilot-cli", "devpilot-agent"):
        try:
            return version(distribution)
        except PackageNotFoundError:
            continue
    return "unknown"


class DevPilotAcpAgent(Agent):
    def __init__(self, store: AcpSessionStore | None = None) -> None:
        self._client: Client | None = None
        self._store = store or AcpSessionStore()
        self._sessions: dict[str, AcpSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._cancelled: set[str] = set()

    def on_connect(self, conn: Client) -> None:
        self._client = conn

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        del client_capabilities, client_info, kwargs
        return InitializeResponse(
            protocol_version=protocol_version,
            agent_capabilities=AgentCapabilities(
                load_session=True,
                prompt_capabilities=PromptCapabilities(image=False, audio=False, embedded_context=False),
                mcp_capabilities=McpCapabilities(http=False, sse=False, acp=False),
                session_capabilities=SessionCapabilities(
                    list=SessionListCapabilities(),
                    resume=SessionResumeCapabilities(),
                    close=SessionCloseCapabilities(),
                ),
            ),
            agent_info=Implementation(
                name="devpilot",
                title="DevPilot Autonomous Research",
                version=_runtime_version(),
            ),
        )

    async def new_session(
        self,
        cwd: str,
        additional_directories: list[str] | None = None,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        del additional_directories, mcp_servers, kwargs
        project = Path(cwd).expanduser().resolve()
        if not project.is_dir():
            raise ValueError(f"project directory is not accessible: {project}")
        session_id = uuid4().hex
        session = AcpSession(session_id=session_id, cwd=project, run_name=f"acp-{session_id}")
        self._remember(session)
        return NewSessionResponse(
            session_id=session_id,
            modes=self._mode_state(session),
            config_options=self._config_options(session),
        )

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[Any] | None = None,
        additional_directories: list[str] | None = None,
        **kwargs: Any,
    ) -> LoadSessionResponse:
        del mcp_servers, additional_directories, kwargs
        session = self._require_session(session_id)
        requested_cwd = Path(cwd).expanduser().resolve()
        if requested_cwd != session.cwd:
            raise ValueError(f"session {session_id} belongs to {session.cwd}, not {requested_cwd}")
        return LoadSessionResponse(
            modes=self._mode_state(session),
            config_options=self._config_options(session),
        )

    async def resume_session(
        self,
        session_id: str,
        cwd: str,
        additional_directories: list[str] | None = None,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> ResumeSessionResponse:
        loaded = await self.load_session(
            cwd=cwd,
            session_id=session_id,
            mcp_servers=mcp_servers,
            additional_directories=additional_directories,
            **kwargs,
        )
        return ResumeSessionResponse(modes=loaded.modes, config_options=loaded.config_options)

    async def list_sessions(
        self,
        cwd: str | None = None,
        cursor: str | None = None,
        **kwargs: Any,
    ) -> ListSessionsResponse:
        del cursor, kwargs
        sessions = [
            SessionInfo(
                session_id=session.session_id,
                cwd=str(session.cwd),
                title=session.title or f"DevPilot {session.mode} run",
                updated_at=session.updated_at,
            )
            for session in self._store.list(cwd=cwd)
        ]
        return ListSessionsResponse(sessions=sessions)

    async def set_session_mode(
        self,
        session_id: str,
        mode_id: str,
        **kwargs: Any,
    ) -> SetSessionModeResponse:
        del kwargs
        if mode_id not in MODE_IDS:
            raise ValueError(f"unsupported DevPilot mode: {mode_id}")
        session = self._require_session(session_id)
        session.mode = mode_id
        self._remember(session)
        return SetSessionModeResponse()

    async def set_config_option(
        self,
        config_id: str,
        session_id: str,
        value: str | bool,
        **kwargs: Any,
    ) -> SetSessionConfigOptionResponse:
        del kwargs
        session = self._require_session(session_id)
        if config_id == "reasoningEffort" and isinstance(value, str):
            if value not in {"low", "medium", "high", "max"}:
                raise ValueError(f"unsupported reasoning effort: {value}")
            session.reasoning_effort = value
        elif config_id == "model" and isinstance(value, str) and value.strip():
            session.model = value.strip()
        else:
            raise ValueError(f"unsupported DevPilot config option: {config_id}")
        self._remember(session)
        return SetSessionConfigOptionResponse(config_options=self._config_options(session))

    async def prompt(self, session_id: str, prompt: list[Any], **kwargs: Any) -> PromptResponse:
        del kwargs
        session = self._require_session(session_id)
        message = extract_prompt_text(prompt)
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        if lock.locked():
            raise RuntimeError(f"session {session_id} already has an active prompt")

        async with lock:
            self._cancelled.discard(session_id)
            invocation = build_run_invocation(session, message)
            process_group_options = (
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                if sys.platform == "win32"
                else {"start_new_session": True}
            )
            process = await asyncio.create_subprocess_exec(
                *invocation,
                cwd=str(session.cwd),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **process_group_options,
            )
            session.process = process
            stderr_task = asyncio.create_task(self._forward_stderr(process))
            try:
                assert process.stdout is not None
                while True:
                    raw = await process.stdout.readline()
                    if not raw:
                        break
                    line = raw.decode("utf-8", errors="replace").rstrip()
                    if line:
                        await self._send_text_update(session_id, line)
                return_code = await process.wait()
                await stderr_task
            finally:
                session.process = None

            if session_id in self._cancelled:
                self._remember(session)
                return PromptResponse(stop_reason="cancelled")
            if return_code != 0:
                raise RuntimeError(f"DevPilot run exited with code {return_code}")
            session.has_started = True
            session.title = message.splitlines()[0][:120]
            self._remember(session)
            return PromptResponse(stop_reason="end_turn")

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        del kwargs
        session = self._require_session(session_id)
        self._cancelled.add(session_id)
        process = session.process
        if process is None or process.returncode is not None:
            return
        try:
            if sys.platform == "win32":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGINT)
        except (ProcessLookupError, OSError, ValueError):
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=10)
        except asyncio.TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()

    async def close_session(self, session_id: str, **kwargs: Any) -> CloseSessionResponse:
        await self.cancel(session_id, **kwargs)
        self._sessions.pop(session_id, None)
        self._locks.pop(session_id, None)
        return CloseSessionResponse()

    async def _send_text_update(self, session_id: str, text: str) -> None:
        if self._client is None:
            return
        await self._client.session_update(
            session_id=session_id,
            update=update_agent_message(text_block(f"{text}\n")),
            source="devpilot",
        )

    @staticmethod
    async def _forward_stderr(process: asyncio.subprocess.Process) -> None:
        assert process.stderr is not None
        while True:
            raw = await process.stderr.readline()
            if not raw:
                break
            text = raw.decode("utf-8", errors="replace")
            sys.stderr.write(text)
            sys.stderr.flush()

    def _remember(self, session: AcpSession) -> None:
        self._sessions[session.session_id] = session
        self._store.save(session)

    def _require_session(self, session_id: str) -> AcpSession:
        session = self._sessions.get(session_id) or self._store.load(session_id)
        if session is None:
            raise ValueError(f"unknown DevPilot ACP session: {session_id}")
        self._sessions[session_id] = session
        return session

    @staticmethod
    def _mode_state(session: AcpSession) -> SessionModeState:
        return SessionModeState(
            current_mode_id=session.mode,
            available_modes=[
                SessionMode(id=mode.id, name=mode.name, description=mode.description)
                for mode in DEVPILOT_MODES
            ],
        )

    @staticmethod
    def _config_options(session: AcpSession) -> list[SessionConfigOptionSelect]:
        reasoning_effort = session.reasoning_effort or "medium"
        options = [
            SessionConfigOptionSelect(
                type="select",
                id="reasoningEffort",
                name="Reasoning effort",
                description="How much reasoning effort the selected provider should use.",
                current_value=reasoning_effort,
                options=[
                    SessionConfigSelectOption(value=value, name=value.title())
                    for value in ("low", "medium", "high", "max")
                ],
            )
        ]
        if session.model:
            options.append(
                SessionConfigOptionSelect(
                    type="select",
                    id="model",
                    name="Model",
                    description="Model selected from the DevPilot runtime configuration.",
                    current_value=session.model,
                    options=[SessionConfigSelectOption(value=session.model, name=session.model)],
                )
            )
        return options


async def run_stdio_agent() -> None:
    await run_agent(DevPilotAcpAgent(), use_unstable_protocol=True)
