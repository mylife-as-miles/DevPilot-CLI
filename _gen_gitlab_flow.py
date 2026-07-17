"""Generate GitLab Duo flow configs from DevPilot mega-prompt files."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent
OUT_DIR = _ROOT / "gitlab-flow"

PROMPTS = {
    "intake": _ROOT / "GITLAB_INTAKE_MEGA_PROMPT.txt",
    "coordinator": _ROOT / "GITLAB_COORDINATOR_MEGA_PROMPT.txt",
    "executor": _ROOT / "GITLAB_EXECUTOR_MEGA_PROMPT.txt",
    "search": _ROOT / "GITLAB_SEARCH_MEGA_PROMPT.txt",
}

ORBIT_TOOLS = [
    "orbit_list_commands",
    "orbit_invoke_command",
    "orbit_query_graph",
    "orbit_get_graph_schema",
    "orbit_get_graph_status",
]

COMMON_READ = [
    "get_repository_file",
    "list_repository_tree",
    "gitlab_blob_search",
    "find_files",
    "grep",
    "read_file",
]

WORK_ITEMS = [
    "list_work_items",
    "get_work_item",
    "create_work_item",
    "update_work_item",
    "create_work_item_note",
    "create_plan",
    "get_plan",
    "add_new_task",
]

CI_TOOLS = [
    "get_pipeline_errors",
    "get_job_logs",
    "ci_linter",
    "run_tests",
]

MR_TOOLS = [
    "get_merge_request",
    "list_merge_request_diffs",
    "create_merge_request",
    "create_merge_request_note",
]

EXECUTOR_TOOLS = [
    "edit_file",
    "create_file_with_contents",
    "mkdir",
    "run_command",
    "run_git_command",
    "run_tests",
]

SEARCH_TOOLS = [
    "gitlab_blob_search",
    "grep",
    "read_file",
    "gitlab_documentation_search",
    "gitlab_issue_search",
    "gitlab_merge_request_search",
]

REPO_PROMPT_PATHS = {
    "intake": "GITLAB_INTAKE_MEGA_PROMPT.txt",
    "coordinator": "GITLAB_COORDINATOR_MEGA_PROMPT.txt",
    "executor": "GITLAB_EXECUTOR_MEGA_PROMPT.txt",
    "search": "GITLAB_SEARCH_MEGA_PROMPT.txt",
}

SLIM_INTAKE_STUB = f"""You are DevPilot intake (planning agent).

**First turn (required):** use `get_repository_file` to load `{REPO_PROMPT_PATHS["intake"]}`
from the repository default branch. Follow that file exactly — it is the full system prompt.

If the file is missing, tell the user to commit the DevPilot mega-prompt files to this project.

Project: gitlab-ai-hackathon/transcend/35314637
Output: a complete research contract only. Do not run the coordinator loop.
"""

SLIM_COORDINATOR_STUB = f"""You are DevPilot coordinator (persistent research director).

**First turn (required):** use `get_repository_file` to load `{REPO_PROMPT_PATHS["coordinator"]}`
from the repository default branch. Follow that file exactly — it is the full system prompt.

If the file is missing, tell the user to commit the DevPilot mega-prompt files to this project.

You run as a **single persistent ReAct loop** (native DevPilot model). Do not hand off to
separate catalog agents. Use git/repo/CI tools as RunExecutor; persist the Idea Tree at
`.devpilot/sessions/{{{{run_name}}}}/.coordinator/idea_tree.json`; write REPORT.md when done.
"""

HUB_OVERLAY = """
================================================================================
SECTION F — GITLAB FLOW RUNTIME (coordinator hub — matches native DevPilot)
================================================================================

You are the **persistent coordinator ReAct loop**. Native DevPilot runs you as a
single long-lived agent (`CoordinatorOrchestrator`); this flow does the same in
one AgentComponent session. Do **not** treat executor or search as separate
top-level agents you hand off to.

## Shared state (Idea Tree)

- Persist the Idea Tree at:
  `.devpilot/sessions/{{run_name}}/.coordinator/idea_tree.json`
- Create/update it with repository file tools every cycle.
- Schema mirrors DevPilot v3: `meta` (baseline_score, trunk_score, eval_cmd, …)
  and `nodes` (id, parent, hypothesis, status, score, insight, related_work).
- Pass `run_name` from flow input or default to `gitlab-flow-<timestamp>`.

## Tool mapping (native → GitLab)

| Native tool | GitLab substitute |
|-------------|-------------------|
| RunExecutor | `run_git_command` (branch/worktree), `edit_file`, `run_command`, `run_tests` |
| GitMergeBranch | `create_merge_request` + protected-path discipline from merge-eval skill |
| SearchIdeaContext | Inline novelty search **after** node is done/merged **and** beats trunk; write `related_work` on the node |
| TreeView / TreeAddNode / … | Read/write `idea_tree.json` |

## Cycle protocol

Repeat INIT (once) → OBSERVE → IDEATE → SELECT → DISPATCH → DECIDE until:

- `max_cycles` flow input is reached (default **3**), or
- diminishing returns / budget stop, or
- user goal satisfied.

**DISPATCH:** implement the selected idea yourself via git isolation + code edits +
B_dev eval. You are the coordinator; executors are a role you perform via tools,
not a separate flow stage.

**Search:** only for validated winners (status done/merged, score > trunk). Do not
block the next IDEATE round on search — note `related_work` when ready.

## End of run

Write `.devpilot/sessions/{{run_name}}/REPORT.md` and end with status **complete**.
"""

ROUTE_GATE_PROMPT = """You are a routing gate for the DevPilot GitLab flow.

Read the coordinator cycle output below. Reply with **exactly one token** and nothing else:

- `dispatch_executor` — coordinator selected an idea and wants an isolated executor pass
- `dispatch_search` — a validated winner needs novelty / related-work annotation
- `complete` — run finished (REPORT.md written or budget exhausted)

Choose `dispatch_executor` only when the coordinator explicitly queued an experiment
with a concrete hypothesis and node id. Choose `dispatch_search` only when a node
beat trunk and needs related_work. Otherwise prefer `complete` if REPORT exists or
max cycles reached; else `dispatch_executor` if a node is `running`.

Coordinator output:
{{coordinator_output}}
"""

PROMPT_REPO_FILES = {
    "intake": "GITLAB_INTAKE_MEGA_PROMPT.txt",
    "coordinator": "GITLAB_COORDINATOR_MEGA_PROMPT.txt",
    "executor": "GITLAB_EXECUTOR_MEGA_PROMPT.txt",
    "search": "GITLAB_SEARCH_MEGA_PROMPT.txt",
}

SLIM_SIZE_LIMIT = 64 * 1024  # GitLab flow version max (64 KiB)

INTAKE_STUB = """You are DevPilot intake and planning.

FIRST ACTION (mandatory before anything else):
  Read `GITLAB_INTAKE_MEGA_PROMPT.txt` from this repository (default branch)
  using get_repository_file. Follow that file exactly — it is your full system
  prompt, GitLab bindings, and output contract.

Project: gitlab-ai-hackathon/transcend/35314637

Scope: intake and planning only. Do not run the coordinator optimization loop.
"""

COORDINATOR_HUB_STUB = """You are DevPilot coordinator — one persistent ReAct loop (native architecture).

FIRST ACTION (mandatory before anything else):
  Read `GITLAB_COORDINATOR_MEGA_PROMPT.txt` from this repository (default branch)
  using get_repository_file. Follow that file for the full DevPilot cycle protocol.

Then apply these GitLab flow runtime rules:
""" + HUB_OVERLAY

EXECUTOR_STUB = """You are DevPilot executor.

FIRST ACTION (mandatory): Read `GITLAB_EXECUTOR_MEGA_PROMPT.txt` from the
repository (default branch) via get_repository_file. Follow it exactly.

Implement one dispatched experiment; evaluate on B_dev only; return structured report.
"""

SEARCH_STUB = """You are DevPilot search / novelty agent.

FIRST ACTION (mandatory): Read `GITLAB_SEARCH_MEGA_PROMPT.txt` from the
repository (default branch) via get_repository_file. Follow it exactly.

Run related-work survey only for validated winners. Return mandatory JSON + Markdown.
"""

ROUTE_GATE_STUB = """Reply with exactly one token and nothing else:
dispatch_executor | dispatch_search | complete

Read the coordinator output and choose:
- dispatch_executor — concrete experiment queued with node id
- dispatch_search — validated winner beat trunk, needs related_work
- complete — REPORT.md done or budget exhausted
"""

REPORT_PROMPT = """You finalize a DevPilot research run on GitLab.

Read the idea tree and cycle artifacts. Produce or update
`.devpilot/sessions/{{run_name}}/REPORT.md` with:

1. Goal and metric
2. Baseline vs trunk vs best node
3. Merged improvements (MR links if any)
4. Pruned / failed branches (brief)
5. Open questions

Use repository read/write tools. Keep REPORT concise and factual.
"""


def _body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    marker = "SECTION A —"
    idx = text.find(marker)
    if idx == -1:
        return text.strip()
    return text[idx:].strip()


def _yaml_literal(s: str, indent: int = 8) -> str:
    pad = " " * indent
    return "\n".join(pad + line for line in s.splitlines())


def _tool_lines(tools: list[str], indent: int = 6) -> str:
    pad = " " * indent
    return "\n".join(f'{pad}- "{t}"' for t in tools)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Wrote {path} ({path.stat().st_size:,} bytes)")


def generate_slim_hub() -> None:
    """Under GitLab's 64 KiB custom-flow version limit."""
    hub_tools = COMMON_READ + WORK_ITEMS + ORBIT_TOOLS + CI_TOOLS + MR_TOOLS + EXECUTOR_TOOLS + SEARCH_TOOLS
    coordinator_stub = SLIM_COORDINATOR_STUB + "\n" + HUB_OVERLAY

    yaml = f"""# DevPilot — GitLab flow (slim, under 64 KiB)
# Prompts load from repo files at runtime. Commit GITLAB_*_MEGA_PROMPT.txt first.
# For catalog agents instead of a flow, see gitlab-flow/AGENT_SETUP.md

version: "v1"
environment: ambient

components:
  - name: "devpilot_intake"
    type: AgentComponent
    prompt_id: "devpilot_intake_prompt"
    inputs:
      - from: "context:goal"
        as: "user_goal"
      - from: "context:project_id"
        as: "project_id"
      - from: "context:run_name"
        as: "run_name"
    toolset:
{_tool_lines(COMMON_READ + WORK_ITEMS + ORBIT_TOOLS)}
    ui_log_events:
      - "on_agent_final_answer"

  - name: "devpilot_coordinator_hub"
    type: AgentComponent
    prompt_id: "devpilot_coordinator_hub_prompt"
    inputs:
      - from: "context:goal"
        as: "user_goal"
      - from: "context:project_id"
        as: "project_id"
      - from: "context:run_name"
        as: "run_name"
      - from: "context:max_cycles"
        as: "max_cycles"
      - from: "context:devpilot_intake.final_answer"
        as: "research_contract"
    toolset:
{_tool_lines(hub_tools)}
    ui_log_events:
      - "on_agent_final_answer"

routers:
  - from: "devpilot_intake"
    to: "devpilot_coordinator_hub"
  - from: "devpilot_coordinator_hub"
    to: "end"

flow:
  entry_point: "devpilot_intake"

prompts:
  - name: "DevPilot Intake"
    prompt_id: "devpilot_intake_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(SLIM_INTAKE_STUB)}
      user: |
        Project ID: {{{{project_id}}}}
        Run name: {{{{run_name}}}}
        Goal: {{{{user_goal}}}}
      placeholder: history
    params:
      timeout: 300

  - name: "DevPilot Coordinator Hub"
    prompt_id: "devpilot_coordinator_hub_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(coordinator_stub)}
      user: |
        Project ID: {{{{project_id}}}}
        Run name: {{{{run_name}}}}
        Max cycles: {{{{max_cycles}}}}
        Goal: {{{{user_goal}}}}
        Research contract:
        {{{{research_contract}}}}
      placeholder: history
    params:
      timeout: 1200
"""
    out = OUT_DIR / "devpilot-flow-config.yaml"
    _write(out, yaml)
    if out.stat().st_size > 65536:
        raise SystemExit(f"Slim flow still too large: {out.stat().st_size} bytes")


def generate_hub() -> None:
    intake = _body(PROMPTS["intake"])
    coordinator = _body(PROMPTS["coordinator"]) + "\n\n" + HUB_OVERLAY

    hub_tools = COMMON_READ + WORK_ITEMS + ORBIT_TOOLS + CI_TOOLS + MR_TOOLS + EXECUTOR_TOOLS + SEARCH_TOOLS

    yaml = f"""# DevPilot — GitLab Duo flow (hub / recommended)
# Matches native DevPilot: intake → single persistent coordinator ReAct loop.
# Project: gitlab-ai-hackathon/transcend/35314637

version: "v1"
environment: ambient

components:
  - name: "devpilot_intake"
    type: AgentComponent
    prompt_id: "devpilot_intake_prompt"
    inputs:
      - from: "context:goal"
        as: "user_goal"
      - from: "context:project_id"
        as: "project_id"
      - from: "context:run_name"
        as: "run_name"
    toolset:
{_tool_lines(COMMON_READ + WORK_ITEMS + ORBIT_TOOLS)}
    ui_log_events:
      - "on_agent_final_answer"
      - "on_tool_execution_success"

  - name: "devpilot_coordinator_hub"
    type: AgentComponent
    prompt_id: "devpilot_coordinator_hub_prompt"
    inputs:
      - from: "context:goal"
        as: "user_goal"
      - from: "context:project_id"
        as: "project_id"
      - from: "context:run_name"
        as: "run_name"
      - from: "context:max_cycles"
        as: "max_cycles"
      - from: "context:devpilot_intake.final_answer"
        as: "research_contract"
    toolset:
{_tool_lines(hub_tools)}
    ui_log_events:
      - "on_agent_final_answer"
      - "on_tool_execution_success"
      - "on_tool_execution_failed"

routers:
  - from: "devpilot_intake"
    to: "devpilot_coordinator_hub"
  - from: "devpilot_coordinator_hub"
    to: "end"

flow:
  entry_point: "devpilot_intake"

prompts:
  - name: "DevPilot Intake"
    prompt_id: "devpilot_intake_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(intake)}
      user: |
        Project ID: {{{{project_id}}}}
        Run name: {{{{run_name}}}}

        User goal:
        {{{{user_goal}}}}

        Intake and planning only. Output the research contract. Do not run the
        coordinator optimization loop.
      placeholder: history
    params:
      timeout: 300

  - name: "DevPilot Coordinator Hub"
    prompt_id: "devpilot_coordinator_hub_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(coordinator)}
      user: |
        Project ID: {{{{project_id}}}}
        Run name: {{{{run_name}}}}
        Max cycles: {{{{max_cycles}}}}

        User goal:
        {{{{user_goal}}}}

        Research contract:
        {{{{research_contract}}}}

        Run the full DevPilot coordinator loop in this session. Persist the Idea
        Tree under .devpilot/sessions/{{{{run_name}}}}/. Write REPORT.md when done.
      placeholder: history
    params:
      timeout: 1200
"""
    _write(OUT_DIR / "devpilot-flow-config-full.yaml", yaml)


def generate_loop() -> None:
    intake = _body(PROMPTS["intake"])
    coordinator = _body(PROMPTS["coordinator"])
    executor = _body(PROMPTS["executor"])
    search = _body(PROMPTS["search"])

    cycle_overlay = """
================================================================================
SECTION F — GITLAB LOOP FLOW (one coordinator cycle per invocation)
================================================================================

You run **one** DevPilot cycle step per invocation (OBSERVE → IDEATE → SELECT →
DISPATCH decision). Persist the Idea Tree at
`.devpilot/sessions/{{run_name}}/.coordinator/idea_tree.json`.

End every response with a line:
`FLOW_ROUTE: dispatch_executor | dispatch_search | complete`

- `dispatch_executor` — selected node needs isolated implementation (hand off package below)
- `dispatch_search` — validated winner beats trunk; needs related_work
- `complete` — write REPORT.md and stop

Include a JSON block `idea_tree_snapshot` with the full tree when possible.
"""

    yaml = f"""# DevPilot — GitLab Duo flow (loop / multi-cycle)
# intake → coordinator cycle → route gate → executor OR search OR report → loop back
# Project: gitlab-ai-hackathon/transcend/35314637

version: "v1"
environment: ambient

components:
  - name: "devpilot_intake"
    type: AgentComponent
    prompt_id: "devpilot_intake_prompt"
    inputs:
      - from: "context:goal"
        as: "user_goal"
      - from: "context:project_id"
        as: "project_id"
      - from: "context:run_name"
        as: "run_name"
    toolset:
{_tool_lines(COMMON_READ + WORK_ITEMS + ORBIT_TOOLS)}
    ui_log_events:
      - "on_agent_final_answer"

  - name: "devpilot_coordinator_cycle"
    type: AgentComponent
    prompt_id: "devpilot_coordinator_cycle_prompt"
    inputs:
      - from: "context:goal"
        as: "user_goal"
      - from: "context:project_id"
        as: "project_id"
      - from: "context:run_name"
        as: "run_name"
      - from: "context:max_cycles"
        as: "max_cycles"
      - from: "context:devpilot_intake.final_answer"
        as: "research_contract"
      - from: "context:devpilot_executor.final_answer"
        as: "last_executor_report"
      - from: "context:devpilot_search.final_answer"
        as: "last_search_result"
    toolset:
{_tool_lines(COMMON_READ + WORK_ITEMS + ORBIT_TOOLS + CI_TOOLS + MR_TOOLS)}
    ui_log_events:
      - "on_agent_final_answer"

  - name: "devpilot_route_gate"
    type: AgentComponent
    prompt_id: "devpilot_route_gate_prompt"
    inputs:
      - from: "context:devpilot_coordinator_cycle.final_answer"
        as: "coordinator_output"
    toolset: []
    ui_log_events:
      - "on_agent_final_answer"

  - name: "devpilot_executor"
    type: AgentComponent
    prompt_id: "devpilot_executor_prompt"
    inputs:
      - from: "context:project_id"
        as: "project_id"
      - from: "context:run_name"
        as: "run_name"
      - from: "context:devpilot_coordinator_cycle.final_answer"
        as: "executor_dispatch"
    toolset:
{_tool_lines(COMMON_READ + EXECUTOR_TOOLS + MR_TOOLS + ORBIT_TOOLS)}
    ui_log_events:
      - "on_agent_final_answer"

  - name: "devpilot_search"
    type: AgentComponent
    prompt_id: "devpilot_search_prompt"
    inputs:
      - from: "context:project_id"
        as: "project_id"
      - from: "context:devpilot_coordinator_cycle.final_answer"
        as: "validated_hypothesis"
      - from: "context:devpilot_executor.final_answer"
        as: "experiment_report"
    toolset:
{_tool_lines(SEARCH_TOOLS + ORBIT_TOOLS)}
    ui_log_events:
      - "on_agent_final_answer"

  - name: "devpilot_report"
    type: AgentComponent
    prompt_id: "devpilot_report_prompt"
    inputs:
      - from: "context:goal"
        as: "user_goal"
      - from: "context:run_name"
        as: "run_name"
      - from: "context:project_id"
        as: "project_id"
      - from: "context:devpilot_coordinator_cycle.final_answer"
        as: "coordinator_summary"
    toolset:
{_tool_lines(COMMON_READ + ["edit_file", "create_file_with_contents"])}
    ui_log_events:
      - "on_agent_final_answer"

routers:
  - from: "devpilot_intake"
    to: "devpilot_coordinator_cycle"
  - from: "devpilot_coordinator_cycle"
    to: "devpilot_route_gate"
  - from: "devpilot_route_gate"
    condition:
      input: "context:devpilot_route_gate.final_answer"
      routes:
        "dispatch_executor": "devpilot_executor"
        "dispatch_search": "devpilot_search"
        "complete": "devpilot_report"
        "default_route": "devpilot_coordinator_cycle"
  - from: "devpilot_executor"
    to: "devpilot_coordinator_cycle"
  - from: "devpilot_search"
    to: "devpilot_coordinator_cycle"
  - from: "devpilot_report"
    to: "end"

flow:
  entry_point: "devpilot_intake"

prompts:
  - name: "DevPilot Intake"
    prompt_id: "devpilot_intake_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(intake)}
      user: |
        Project ID: {{{{project_id}}}}
        Run name: {{{{run_name}}}}
        Goal: {{{{user_goal}}}}
      placeholder: history
    params:
      timeout: 300

  - name: "DevPilot Coordinator Cycle"
    prompt_id: "devpilot_coordinator_cycle_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(coordinator + cycle_overlay)}
      user: |
        Project: {{{{project_id}}}}  Run: {{{{run_name}}}}  Max cycles: {{{{max_cycles}}}}
        Goal: {{{{user_goal}}}}
        Contract: {{{{research_contract}}}}
        Last executor report: {{{{last_executor_report}}}}
        Last search result: {{{{last_search_result}}}}
      placeholder: history
    params:
      timeout: 600

  - name: "DevPilot Route Gate"
    prompt_id: "devpilot_route_gate_prompt"
    unit_primitives: []
    prompt_template:
      system: |
        Reply with exactly one routing token. No other text.
      user: |
{_yaml_literal(ROUTE_GATE_PROMPT, indent=8)}
      placeholder: history
    params:
      timeout: 60

  - name: "DevPilot Executor"
    prompt_id: "devpilot_executor_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(executor)}
      user: |
        Project: {{{{project_id}}}}  Run: {{{{run_name}}}}
        Dispatch: {{{{executor_dispatch}}}}
      placeholder: history
    params:
      timeout: 600

  - name: "DevPilot Search"
    prompt_id: "devpilot_search_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(search)}
      user: |
        Project: {{{{project_id}}}}
        Hypothesis: {{{{validated_hypothesis}}}}
        Experiment: {{{{experiment_report}}}}
      placeholder: history
    params:
      timeout: 300

  - name: "DevPilot Report"
    prompt_id: "devpilot_report_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(REPORT_PROMPT)}
      user: |
        Project: {{{{project_id}}}}  Run: {{{{run_name}}}}
        Goal: {{{{user_goal}}}}
        Summary: {{{{coordinator_summary}}}}
      placeholder: history
    params:
      timeout: 300
"""
    _write(OUT_DIR / "devpilot-loop-flow-config.yaml", yaml)


def generate_demo_linear() -> None:
    intake = _body(PROMPTS["intake"])
    coordinator = _body(PROMPTS["coordinator"])
    executor = _body(PROMPTS["executor"])
    search = _body(PROMPTS["search"])

    yaml = f"""# DevPilot — GitLab Duo flow (demo linear — NOT architecturally faithful)
# Single pass: intake → coordinator → executor → search. Use devpilot-flow-config.yaml instead.
# Project: gitlab-ai-hackathon/transcend/35314637

version: "v1"
environment: ambient

components:
  - name: "devpilot_intake"
    type: AgentComponent
    prompt_id: "devpilot_intake_prompt"
    inputs:
      - from: "context:goal"
        as: "user_goal"
      - from: "context:project_id"
        as: "project_id"
    toolset:
{_tool_lines(COMMON_READ + WORK_ITEMS + ORBIT_TOOLS)}
    ui_log_events:
      - "on_agent_final_answer"

  - name: "devpilot_coordinator"
    type: AgentComponent
    prompt_id: "devpilot_coordinator_prompt"
    inputs:
      - from: "context:goal"
        as: "user_goal"
      - from: "context:project_id"
        as: "project_id"
      - from: "context:devpilot_intake.final_answer"
        as: "research_contract"
    toolset:
{_tool_lines(COMMON_READ + WORK_ITEMS + ORBIT_TOOLS + CI_TOOLS + MR_TOOLS)}
    ui_log_events:
      - "on_agent_final_answer"

  - name: "devpilot_executor"
    type: AgentComponent
    prompt_id: "devpilot_executor_prompt"
    inputs:
      - from: "context:project_id"
        as: "project_id"
      - from: "context:devpilot_coordinator.final_answer"
        as: "executor_dispatch"
    toolset:
{_tool_lines(COMMON_READ + EXECUTOR_TOOLS + MR_TOOLS + ORBIT_TOOLS)}
    ui_log_events:
      - "on_agent_final_answer"

  - name: "devpilot_search"
    type: AgentComponent
    prompt_id: "devpilot_search_prompt"
    inputs:
      - from: "context:project_id"
        as: "project_id"
      - from: "context:devpilot_coordinator.final_answer"
        as: "validated_hypothesis"
      - from: "context:devpilot_executor.final_answer"
        as: "experiment_report"
    toolset:
{_tool_lines(SEARCH_TOOLS + ORBIT_TOOLS)}
    ui_log_events:
      - "on_agent_final_answer"

routers:
  - from: "devpilot_intake"
    to: "devpilot_coordinator"
  - from: "devpilot_coordinator"
    to: "devpilot_executor"
  - from: "devpilot_executor"
    to: "devpilot_search"
  - from: "devpilot_search"
    to: "end"

flow:
  entry_point: "devpilot_intake"

prompts:
  - name: "DevPilot Intake"
    prompt_id: "devpilot_intake_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(intake)}
      user: |
        Project ID: {{{{project_id}}}}
        Goal: {{{{user_goal}}}}
      placeholder: history
    params:
      timeout: 300

  - name: "DevPilot Coordinator"
    prompt_id: "devpilot_coordinator_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(coordinator)}
      user: |
        Project: {{{{project_id}}}}
        Goal: {{{{user_goal}}}}
        Contract: {{{{research_contract}}}}
      placeholder: history
    params:
      timeout: 600

  - name: "DevPilot Executor"
    prompt_id: "devpilot_executor_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(executor)}
      user: |
        Project: {{{{project_id}}}}
        Dispatch: {{{{executor_dispatch}}}}
      placeholder: history
    params:
      timeout: 600

  - name: "DevPilot Search"
    prompt_id: "devpilot_search_prompt"
    unit_primitives: []
    prompt_template:
      system: |
{_yaml_literal(search)}
      user: |
        Project: {{{{project_id}}}}
        Hypothesis: {{{{validated_hypothesis}}}}
        Experiment: {{{{experiment_report}}}}
      placeholder: history
    params:
      timeout: 300
"""
    _write(OUT_DIR / "devpilot-demo-linear-flow-config.yaml", yaml)


def main() -> None:
    generate_slim_hub()
    generate_hub()
    generate_loop()
    generate_demo_linear()
    # Back-compat alias for earlier filename
    src = OUT_DIR / "devpilot-demo-linear-flow-config.yaml"
    dst = OUT_DIR / "devpilot-research-flow-config.yaml"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Wrote {dst} (alias, {dst.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
