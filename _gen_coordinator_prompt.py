"""Generate GITLAB_COORDINATOR_MEGA_PROMPT.txt."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parent
PROJECT_PATH = "gitlab-ai-hackathon/transcend/35314637"
SESSION_CWD = str(_ROOT)


def _bootstrap_devpilot():
    spec = importlib.util.spec_from_file_location(
        "devpilot",
        _ROOT / "src" / "__init__.py",
        submodule_search_locations=[str(_ROOT / "src")],
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["devpilot"] = mod
    assert spec.loader
    spec.loader.exec_module(mod)


_bootstrap_devpilot()
from devpilot.coordinator.config import CoordinatorConfig
from devpilot.coordinator.prompts import build_coordinator_system_prompt

skills = {
    "orchestrator": (_ROOT / "skills/devpilot-agent-orchestrator/SKILL.md").read_text(encoding="utf-8"),
    "coordinator": (_ROOT / "skills/devpilot-agent-coordinator/SKILL.md").read_text(encoding="utf-8"),
    "ideate": (_ROOT / "skills/devpilot-agent-ideate/SKILL.md").read_text(encoding="utf-8"),
}
idea_drafting = (_ROOT / "src/skills/idea_drafting.md").read_text(encoding="utf-8")

def _skill_body(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text

coord_prompt = build_coordinator_system_prompt(
    CoordinatorConfig(cwd=SESSION_CWD, max_cycles=40, merge_threshold=0.5)
)

gitlab_bindings = f"""
================================================================================
SECTION E — GITLAB DUO BINDINGS (required adapter; not in original sources)
================================================================================

Project path: {PROJECT_PATH}
Session working directory: use the GitLab repository clone or project context for {PROJECT_PATH}.

This agent receives a completed research contract from the Intake agent (or the user).
Do not repeat full intake. Verify the contract, run INIT, then execute the DevPilot cycle.

Tool mapping (native DevPilot coordinator → GitLab Duo):

Idea Tree / state (no native TreeView on GitLab):
- Use devpilot_state.py from devpilot-agent-tools when available, OR
- Persist state in <project>/.devpilot/sessions/<run_name>/.coordinator/idea_tree.json
- Document tree updates in work item notes or experiment markdown under experiments/<node_id>/

Repository inspection:
- Get Repository File, List Repository Tree, GitLab Blob Search, Grep, Read File, Find Files

Executor dispatch (no native RunExecutor on GitLab):
- Create a work item or issue per experiment: "Executor: <node_id> — <hypothesis summary>"
- Put full executor brief in description: hypothesis, ancestor insights, eval_cmd, files to focus on
- Hand off to the DevPilot Executor agent OR implement via Edit File / Run Command in IDE mode
- Record results back to idea_tree.json and work item when done

Merge / eval:
- Get Merge Request, List Merge Request Diffs, Ci Linter, Get Pipeline Errors, Run Tests
- Never merge on B_dev alone when B_test is required by contract

Related work / Search:
- Orbit: List Commands → Invoke Command (get_graph_schema, get_query_dsl) → query_graph
- GitLab Documentation Search, GitLab Issue Search, GitLab Merge Request Search
- Load devpilot-agent-search behavior when annotating validated winners

Human gates:
- Create Work Item Note, Update Work Item for direction/review checkpoints
- AskUser equivalent: ask in chat and wait for user reply before dispatch

Handoff FROM intake:
- Expect: cwd, instruction (5-component contract), suggested_max_cycles, notes, rationale
- If missing, send user back to Intake agent — do not guess the metric

Handoff TO executor:
- After SELECT, emit executor dispatch artifact with node_id, hypothesis, eval_cmd, additional_context
- Do not write benchmark solution code directly as coordinator

Completion:
- Write REPORT.md under .devpilot/sessions/<run_name>/
- Create final work item summarizing trunk score, test score, merged branches, and caveats
"""

parts = [
    "================================================================================\n",
    "GITLAB DUO CUSTOM AGENT — VERBATIM COORDINATOR MEGA-PROMPT\n",
    "================================================================================\n",
    "Sources (combined verbatim):\n",
    "  1. src/coordinator/prompts.py → build_coordinator_system_prompt()\n",
    "  2. skills/devpilot-agent-orchestrator/SKILL.md\n",
    "  3. skills/devpilot-agent-coordinator/SKILL.md\n",
    "  4. skills/devpilot-agent-ideate/SKILL.md\n",
    "  5. src/skills/idea_drafting.md (loaded during strict IDEATE gate)\n",
    "\n",
    f"Project path: {PROJECT_PATH}\n",
    "\n",
    "Suggested Display name: DevPilot Coordinator Agent\n",
    "Suggested Description: Research director for DevPilot — maintains the Idea Tree, runs INIT/OBSERVE/IDEATE/SELECT/DISPATCH/DECIDE, dispatches executors, and decides merge/prune/stop. Requires a completed research contract from Intake.\n",
    "\n",
    "================================================================================\n",
    "SECTION A — COORDINATOR SYSTEM PROMPT (verbatim, default config)\n",
    "Source: src/coordinator/prompts.py\n",
    "================================================================================\n\n",
    coord_prompt,
    "\n\n================================================================================\n",
    "SECTION B — SKILL: devpilot-agent-orchestrator (verbatim body)\n",
    "Source: skills/devpilot-agent-orchestrator/SKILL.md\n",
    "================================================================================\n\n",
    _skill_body(skills["orchestrator"]),
    "\n\n================================================================================\n",
    "SECTION C — SKILL: devpilot-agent-coordinator (verbatim body)\n",
    "Source: skills/devpilot-agent-coordinator/SKILL.md\n",
    "================================================================================\n\n",
    _skill_body(skills["coordinator"]),
    "\n\n================================================================================\n",
    "SECTION D — SKILL: devpilot-agent-ideate (verbatim body)\n",
    "Source: skills/devpilot-agent-ideate/SKILL.md\n",
    "================================================================================\n\n",
    _skill_body(skills["ideate"]),
    "\n\n================================================================================\n",
    "SECTION D2 — SKILL: idea_drafting (verbatim, strict IDEATE gate)\n",
    "Source: src/skills/idea_drafting.md\n",
    "================================================================================\n\n",
    idea_drafting,
    gitlab_bindings,
]

out = _ROOT / "GITLAB_COORDINATOR_MEGA_PROMPT.txt"
out.write_text("".join(parts), encoding="utf-8")
print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
