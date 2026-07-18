import asyncio
from pathlib import Path

import pytest

from devpilot.acp.agent import DevPilotAcpAgent
from devpilot.acp.store import AcpSessionStore


def test_initialize_advertises_session_lifecycle_capabilities(tmp_path: Path) -> None:
    async def scenario() -> None:
        agent = DevPilotAcpAgent(AcpSessionStore(tmp_path / "store"))
        response = await agent.initialize(protocol_version=1)
        assert response.protocol_version == 1
        assert response.agent_info is not None
        assert response.agent_info.name == "devpilot"
        assert response.agent_capabilities is not None
        assert response.agent_capabilities.load_session is True
        assert response.agent_capabilities.session_capabilities is not None
        assert response.agent_capabilities.session_capabilities.list is not None
        assert response.agent_capabilities.session_capabilities.resume is not None
        assert response.agent_capabilities.session_capabilities.close is not None

    asyncio.run(scenario())


def test_new_session_persists_modes_and_can_be_loaded(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = AcpSessionStore(tmp_path / "store")
        agent = DevPilotAcpAgent(store)
        created = await agent.new_session(cwd=str(tmp_path))
        assert created.modes is not None
        assert created.modes.current_mode_id == "research"
        assert [mode.id for mode in created.modes.available_modes] == [
            "research", "plan", "execute", "review", "audit", "memory"
        ]

        second_agent = DevPilotAcpAgent(store)
        loaded = await second_agent.load_session(cwd=str(tmp_path), session_id=created.session_id)
        assert loaded.modes is not None
        assert loaded.modes.current_mode_id == "research"

    asyncio.run(scenario())


def test_mode_and_reasoning_updates_are_session_scoped(tmp_path: Path) -> None:
    async def scenario() -> None:
        agent = DevPilotAcpAgent(AcpSessionStore(tmp_path / "store"))
        created = await agent.new_session(cwd=str(tmp_path))
        await agent.set_session_mode(created.session_id, "review")
        updated = await agent.set_config_option("reasoningEffort", created.session_id, "high")
        assert any(
            option.id == "reasoningEffort" and option.current_value == "high"
            for option in updated.config_options
        )
        loaded = await agent.load_session(cwd=str(tmp_path), session_id=created.session_id)
        assert loaded.modes is not None
        assert loaded.modes.current_mode_id == "review"

    asyncio.run(scenario())


def test_new_session_rejects_an_inaccessible_project(tmp_path: Path) -> None:
    async def scenario() -> None:
        agent = DevPilotAcpAgent(AcpSessionStore(tmp_path / "store"))
        with pytest.raises(ValueError, match="not accessible"):
            await agent.new_session(cwd=str(tmp_path / "missing"))

    asyncio.run(scenario())
