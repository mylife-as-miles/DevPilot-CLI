"""Generate GITLAB_SEARCH_MEGA_PROMPT.txt."""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent
PROJECT_PATH = "gitlab-ai-hackathon/transcend/35314637"

# Import after bootstrap not needed — static prompts
import importlib.util
import sys

spec = importlib.util.spec_from_file_location(
    "devpilot",
    _ROOT / "src" / "__init__.py",
    submodule_search_locations=[str(_ROOT / "src")],
)
mod = importlib.util.module_from_spec(spec)
sys.modules["devpilot"] = mod
assert spec.loader
spec.loader.exec_module(mod)

from devpilot.search_agent.prompts import (
    SEARCH_AGENT_SYSTEM_PROMPT,
    build_search_user_prompt,
)


def _skill_body(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


skill_search = (_ROOT / "skills/devpilot-agent-search/SKILL.md").read_text(encoding="utf-8")

example_user_prompt = build_search_user_prompt(
    hypothesis=(
        "Mechanism: verifier-guided beam search over candidate answers\n"
        "Hypothesis: Self-verification during decoding reduces reasoning errors on multi-hop QA\n"
        "Observable: Higher exact-match score on B_dev\n"
        "Conflicts: none - attacks verification axis not explored in trunk"
    ),
    ancestor_insights="Prior nodes found retrieval noise dominates failures.",
    focus="Prior art on self-verification for QA, not generic RAG surveys.",
)

gitlab_bindings = f"""
================================================================================
SECTION D — GITLAB DUO BINDINGS (required adapter; not in original sources)
================================================================================

Project path: {PROJECT_PATH}

This agent is dispatched by the Coordinator after a node is validated (done/merged,
score beats trunk). It surveys prior work and returns a novelty annotation.
It does NOT implement ideas or edit benchmark code.

Entry conditions (from Coordinator):
- node_id
- hypothesis (four-line format)
- optional ancestor_insights (background only — do not search for these)
- optional focus directive

Tool mapping (native SearchAgent → GitLab Duo):

External prior-art search:
- GitLab Documentation Search — for GitLab/platform docs only, not academic novelty
- GitLab Blob Search, Grep, Read File — for INTERNAL prior work in this repo/group only
- Orbit: List Commands → Invoke Command (get_graph_schema, get_query_dsl) → query_graph
  — for SDLC graph context (related MRs, issues, dependencies), NOT arxiv papers

For academic/web prior art on GitLab Duo:
- Use any available web search or browse tools if enabled on your agent
- If no web_search/web_visit tools exist, state in output that external search
  was unavailable and run internal-only checks (repo search + Orbit) with
  low-confidence novelty_assessment

Native equivalents when web tools ARE available:
- web_search → batched academic queries (2-3 per round)
- web_visit → fetch and reason over page text with a clear goal

Internal codebase check (supplement, not substitute):
- GitLab Blob Search / Grep for similar implementations in this project
- Orbit query_graph for related merge requests, issues, or modules touching same mechanism

Final deliverable to Coordinator:
1. Emit the mandatory JSON object (see Section A)
2. Also render Markdown for node.related_work:

### Summary
...

### Related Papers
- [Title](url) - relevance

### Novelty
novel | partial-overlap | prior-art-exists - justification

### Overlap Risks
...

3. Update the Coordinator's work item for this node_id with the Markdown block
   OR return JSON + Markdown in your final message for Coordinator to persist

Eligibility — do NOT run if:
- node is pending, running, unscored, or below trunk score
- hypothesis is empty
- request is for trivial parameter tweak with no novelty question

Failure handling:
- If search fails, return valid JSON with related_papers: [] and explain in overlap_risks
- Also provide: [search-failed: <reason>] for Coordinator to store on related_work
- Failures are non-blocking — never gate merge by themselves

Hard caps (unchanged):
- ≤2 search rounds
- ≤5 page visits total
- ≤12 ReAct turns

Handoff FROM Coordinator:
- SearchIdeaContext(node_id, focus?) equivalent

Handoff TO Coordinator:
- JSON + Markdown related_work annotation on node_id
- Coordinator decides merge; you do not merge or edit code
"""

parts = [
    "================================================================================\n",
    "GITLAB DUO CUSTOM AGENT — VERBATIM SEARCH AGENT MEGA-PROMPT\n",
    "================================================================================\n",
    "Sources (combined verbatim):\n",
    "  1. src/search_agent/prompts.py → SEARCH_AGENT_SYSTEM_PROMPT\n",
    "  2. src/search_agent/prompts.py → build_search_user_prompt() example\n",
    "  3. skills/devpilot-agent-search/SKILL.md\n",
    "\n",
    f"Project path: {PROJECT_PATH}\n",
    "\n",
    "Suggested Display name: DevPilot Search Agent\n",
    "Suggested Description: Novelty scout for DevPilot — surveys prior work for a validated hypothesis and returns structured novelty assessment. Dispatched by Coordinator before merge decisions; does not implement or critique ideas.\n",
    "\n",
    "================================================================================\n",
    "SECTION A — SEARCH AGENT SYSTEM PROMPT (verbatim)\n",
    "Source: src/search_agent/prompts.py\n",
    "================================================================================\n\n",
    SEARCH_AGENT_SYSTEM_PROMPT,
    "\n\n================================================================================\n",
    "SECTION B — USER PROMPT TEMPLATE (verbatim builder + example)\n",
    "Source: src/search_agent/prompts.py → build_search_user_prompt()\n",
    "================================================================================\n\n",
    "The Coordinator (or user) should send a user message in this shape:\n\n",
    example_user_prompt,
    "\n\n================================================================================\n",
    "SECTION C — SKILL: devpilot-agent-search (verbatim body)\n",
    "Source: skills/devpilot-agent-search/SKILL.md\n",
    "================================================================================\n\n",
    _skill_body(skill_search),
    gitlab_bindings,
]

out = _ROOT / "GITLAB_SEARCH_MEGA_PROMPT.txt"
out.write_text("".join(parts), encoding="utf-8")
print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
