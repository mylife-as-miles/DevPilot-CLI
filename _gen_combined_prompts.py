"""One-off script to generate COMBINED_AGENT_PROMPTS.md."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod

# Minimal bootstrap: load leaf modules by file path to avoid heavy deps.
_coord_cfg = _load_module("devpilot.coordinator.config", _ROOT / "src" / "coordinator" / "config.py")
_coord_prompts = _load_module("devpilot.coordinator.prompts", _ROOT / "src" / "coordinator" / "prompts.py")
_agent_cfg = _load_module("devpilot.core.config", _ROOT / "src" / "core" / "config.py")
_exec_prompts = _load_module("devpilot.executor.prompts", _ROOT / "src" / "executor" / "prompts.py")
_intake = _load_module("devpilot.cli.intake.system_prompt", _ROOT / "src" / "cli" / "intake" / "system_prompt.py")
_search = _load_module("devpilot.search_agent.prompts", _ROOT / "src" / "search_agent" / "prompts.py")
_context = _load_module("devpilot.core.context", _ROOT / "src" / "core" / "context.py")

CoordinatorConfig = _coord_cfg.CoordinatorConfig
build_coordinator_system_prompt = _coord_prompts.build_coordinator_system_prompt
AgentConfig = _agent_cfg.AgentConfig
executor_prompt = _exec_prompts.build_system_prompt
intake_prompt = _intake.build_system_prompt
SEARCH_AGENT_SYSTEM_PROMPT = _search.SEARCH_AGENT_SYSTEM_PROMPT
COMPACT_SYSTEM_PROMPT = _context.COMPACT_SYSTEM_PROMPT

_COMPANION_PATH = _ROOT / "src" / "cli" / "companion.py"
_companion_src = _COMPANION_PATH.read_text(encoding="utf-8")

def _extract_triple_quoted(name: str) -> str:
    marker = f'{name} = """'
    start = _companion_src.index(marker) + len(marker)
    end = _companion_src.index('"""', start)
    return _companion_src[start:end]

_SYSTEM_PROMPT = _extract_triple_quoted("_SYSTEM_PROMPT")
_GATE_SYSTEM_PROMPT = _extract_triple_quoted("_GATE_SYSTEM_PROMPT")

_POST_RUN_TEMPLATE = """You are DevPilot's post-run assistant.

The research run has already finished. Help the user inspect and understand
the completed run. Answer in the same language the user uses.

Context:
- Project directory: <project_cwd>
- Session directory: <session_dir>
- Final report: <report_path>
- Original instruction: <instruction>

Important behavior:
- For questions about results, decisions, scores, ideas, or artifacts, read
  the final report path first when it exists. Then inspect idea_tree.json,
  idea_tree.md, run_stats.json, events.jsonl, or project files if the report
  is insufficient.
- This follow-up mode is read-only. You cannot start a new experiment, edit
  files, or run shell commands here.
- If the user wants to continue work, give a concrete next `devpilot run ...`
  command and a refined instruction, but do not claim another run has started.
- Keep answers concise unless the user asks for detail. Use Markdown when it
  improves readability."""

cwd = str(_ROOT)
out = _ROOT / "COMBINED_AGENT_PROMPTS.md"

sections: list[str] = [
    "# DevPilot Combined Agent Prompts\n\n",
    "> Generated from source. Dynamic paths use this checkout.\n\n",
    "---\n\n## 1. Intake / Planning Agent\n\n",
    intake_prompt(starting_cwd=cwd),
    "\n\n---\n\n## 2. Coordinator\n\n",
    build_coordinator_system_prompt(CoordinatorConfig(cwd=cwd)),
    "\n\n---\n\n## 3. Executor\n\n",
    executor_prompt(AgentConfig(cwd=cwd)),
    "\n\n---\n\n## 4. Search Agent\n\n",
    SEARCH_AGENT_SYSTEM_PROMPT,
    "\n\n---\n\n## 5a. Companion (read-only Q&A)\n\n",
    _SYSTEM_PROMPT,
    "\n\n---\n\n## 5b. Companion (gate discussion)\n\n",
    _GATE_SYSTEM_PROMPT,
    "\n\n---\n\n## 6. Post-run Follow-up (template)\n\n",
    _POST_RUN_TEMPLATE,
    "\n\n---\n\n## 7. Context Compression (internal)\n\n",
    COMPACT_SYSTEM_PROMPT,
    "\n\n---\n\n## 8. Nested Executor Tool\n\n",
    "Spawns a child agent with the **parent's same system prompt and tools**. "
    "The parent passes a detailed task brief; the child has no conversation memory. "
    "See `src/core/tools/executor_tool.py`.\n",
]

out.write_text("".join(sections), encoding="utf-8")
print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
