import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from acp import PROTOCOL_VERSION, spawn_agent_process
from acp.interfaces import Client


class _SmokeClient(Client):
    async def request_permission(self, session_id, tool_call, options, **kwargs: Any):
        return {"outcome": {"outcome": "cancelled"}}

    async def session_update(self, session_id, update, **kwargs: Any) -> None:
        return None


def test_stdio_handshake_session_modes_and_resume(tmp_path: Path) -> None:
    async def scenario() -> None:
        env = {
            **os.environ,
            "DEVPILOT_ACP_SESSION_DIR": str(tmp_path / "sessions"),
        }
        async with spawn_agent_process(
            _SmokeClient(),
            sys.executable,
            "-m",
            "devpilot.cli.app",
            "acp",
            "--stdio",
            cwd=tmp_path,
            env=env,
            use_unstable_protocol=True,
        ) as (connection, _process):
            initialized = await connection.initialize(protocol_version=PROTOCOL_VERSION)
            assert initialized.protocol_version == PROTOCOL_VERSION
            assert initialized.agent_info is not None
            assert initialized.agent_info.name == "devpilot"

            created = await connection.new_session(cwd=str(tmp_path), mcp_servers=[])
            assert created.modes is not None
            assert created.modes.current_mode_id == "research"
            await connection.set_session_mode(session_id=created.session_id, mode_id="plan")
            resumed = await connection.resume_session(
                cwd=str(tmp_path),
                session_id=created.session_id,
                mcp_servers=[],
            )
            assert resumed.modes is not None
            assert resumed.modes.current_mode_id == "plan"
            await connection.close_session(session_id=created.session_id)

    asyncio.run(scenario())
