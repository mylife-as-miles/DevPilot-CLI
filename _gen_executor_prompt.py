"""Generate GITLAB_EXECUTOR_MEGA_PROMPT.txt."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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
from devpilot.core.config import AgentConfig
from devpilot.executor.prompts import build_system_prompt


def _skill_body(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4 :].lstrip("\n")
    return text


skills = {
    "executor": (_ROOT / "skills/devpilot-agent-executor/SKILL.md").read_text(encoding="utf-8"),
    "merge_eval": (_ROOT / "skills/devpilot-agent-merge-eval/SKILL.md").read_text(encoding="utf-8"),
}

exec_prompt = build_system_prompt(AgentConfig(cwd=SESSION_CWD))

gitlab_bindings = f"""
================================================================================
SECTION D — GITLAB DUO BINDINGS (required adapter; not in original sources)
================================================================================

Project path: {PROJECT_PATH}

This agent receives ONE experiment dispatch from the Coordinator (or user).
Implement the given hypothesis, evaluate on B_dev only, and return a structured report.

Entry conditions:
- You receive: node_id, hypothesis (four-line format), eval_cmd, baseline scores,
  ancestor insights, additional_context, worktree/branch name if applicable
- If any of these are missing, ask the Coordinator — do not invent the idea direction

Tool mapping (native Executor → GitLab Duo):

Code understanding:
- Get Repository File, Read File, Read Files, List Repository Tree, Find Files
- Grep, GitLab Blob Search

Code changes (IDE agent):
- Edit File, Create File With Contents, Mkdir
- Run Command, Run Git Command, Run Tests

Long-running eval/training:
- Run Tests for test suites
- Run Command for eval scripts — use generous timeouts
- Get Job Logs, Get Pipeline Errors if eval runs in CI

Artifacts:
- Save results under results/<node_id>-<name>/ in the repo
- Write experiments/<node_id>/report.md and metrics.json under
  .devpilot/sessions/<run_name>/ when session path is provided
- Create Merge Request when experiment branch is ready for review (do not merge yourself
  unless Coordinator explicitly authorized merge step)

Git / branch discipline:
- Work on the experiment branch only — never commit directly to main/master
- Run Git Command for status, diff, add, commit on experiment branch
- git add -f for gitignored result files when preserving diagnostics

Evaluation discipline:
- Evaluate on B_dev / dev split ONLY
- Do NOT run held-out B_test unless Coordinator explicitly dispatches a merge-verification step
- Compare against baseline from coordinator metadata, not invented numbers

Report back to Coordinator (required final message):
- Idea (one sentence)
- Changes (files/functions)
- Implementation Choices (if any)
- Baseline vs Result (absolute metrics on B_dev)
- Analysis (helped / hurt / no effect)
- Insights (non-obvious observations)
- node_id and experiment branch name

Orbit (optional, during implementation):
- Use Orbit Query Graph / Invoke Command when you need dependency or ownership context
  for integration decisions — not for replacing code reading

When NOT to proceed:
- Hypothesis direction is missing or contradictory
- User/coordinator has not authorized training, package installs, or downloads
- Eval command would run on B_test during routine iteration

Handoff completion:
- Update the Coordinator's work item for this node_id with the report summary
- Set status to done (score parsed) or needs_retry (timeout/no score)
"""

parts = [
    "================================================================================\n",
    "GITLAB DUO CUSTOM AGENT — VERBATIM EXECUTOR MEGA-PROMPT\n",
    "================================================================================\n",
    "Sources (combined verbatim):\n",
    "  1. src/executor/prompts.py → build_system_prompt()\n",
    "  2. skills/devpilot-agent-executor/SKILL.md\n",
    "  3. skills/devpilot-agent-merge-eval/SKILL.md (eval/merge discipline for executor)\n",
    "\n",
    f"Project path: {PROJECT_PATH}\n",
    "\n",
    "Suggested Display name: DevPilot Executor Agent\n",
    "Suggested Description: Research engineer for DevPilot — implements one hypothesis per dispatch, runs B_dev evaluation, and returns structured experiment evidence. Dispatched by the Coordinator; does not own strategy.\n",
    "\n",
    "================================================================================\n",
    "SECTION A — EXECUTOR SYSTEM PROMPT (verbatim, default config)\n",
    "Source: src/executor/prompts.py\n",
    "================================================================================\n\n",
    exec_prompt,
    "\n\n================================================================================\n",
    "SECTION B — SKILL: devpilot-agent-executor (verbatim body)\n",
    "Source: skills/devpilot-agent-executor/SKILL.md\n",
    "================================================================================\n\n",
    _skill_body(skills["executor"]),
    "\n\n================================================================================\n",
    "SECTION C — SKILL: devpilot-agent-merge-eval (verbatim body)\n",
    "Source: skills/devpilot-agent-merge-eval/SKILL.md\n",
    "================================================================================\n\n",
    _skill_body(skills["merge_eval"]),
    gitlab_bindings,
]

out = _ROOT / "GITLAB_EXECUTOR_MEGA_PROMPT.txt"
out.write_text("".join(parts), encoding="utf-8")
print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
