# DevPilot CLI

DevPilot CLI is a local-first developer agent for running structured research on a codebase. It turns a goal into a hypothesis tree, dispatches executor agents into isolated worktrees, records evidence, and carries reusable lessons into future runs.

This project was prepared for OpenAI Build Week in the **Developer Tools** category. It was built with Codex and GPT-5.6 to make DevPilot easier to install, easier to judge, and more useful as a persistent-memory coding assistant.

## Links

- Repository: https://github.com/mylife-as-miles/DevPilot-CLI
- Electron app: https://github.com/mylife-as-miles/DevPilot
- Landing page: https://devpilot-cli-landing.myles4miles.chatgpt.site
- Package name: `miles-devpilot-cli`
- License: Apache-2.0

## What It Does

DevPilot helps a developer run disciplined autonomous improvement loops:

1. The user points DevPilot at a local project.
2. DevPilot collects a goal, constraints, metric, and budget.
3. A Coordinator agent grows a hypothesis tree.
4. Executor agents test individual ideas in isolated git worktrees.
5. Evidence, reports, failures, and successful strategies are saved locally.
6. The learning layer mines memories, reusable skills, and compressed trajectories for later runs.

The goal is not just to "ask an agent to edit code." The goal is to make agentic coding more inspectable, repeatable, and evidence-driven.

## Why This Matters

Most coding agents are good at a single task but weak at remembering what worked across a project. DevPilot focuses on:

- **Local-first execution**: project data stays on the user's machine unless they configure a model provider.
- **Research discipline**: every idea is tracked as a hypothesis with evidence.
- **Safe experimentation**: executor work happens in git branches/worktrees.
- **Learned memory**: previous reports and evidence become compact lessons and reusable skills.
- **Judge-friendly operation**: the CLI can be smoke-tested without running a long autonomous session.

## Built With Codex And GPT-5.6

Codex and GPT-5.6 were used to accelerate the Build Week work in several concrete places:

- Added and refined GPT-5.6 model setup flows, including Sol, Terra, and Luna model choices.
- Built a DevPilot Learning Layer inspired by self-improving agent systems, implemented natively for DevPilot.
- Added local memory extraction, skill mining, trajectory compression, and learned-memory prompt context.
- Added judge-facing install and test instructions.
- Built and deployed the DevPilot CLI landing page from the DevPilot desktop onboarding design.
- Generated a small Devpost-ready project zip under the 35 MB limit.

Codex was especially useful for repository-wide edits: following CLI command registration, preserving existing Typer command patterns, adding tests around local JSONL storage, and verifying build or packaging outputs.

## Related DevPilot App

The companion Electron app lives at https://github.com/mylife-as-miles/DevPilot. That repository contains the local desktop control plane for DevPilot, including the Electron shell in `apps/desktop` and the UI source in `apps/ui`.

This CLI repository is the command-line runtime and judge-testable developer tool. The Build Week landing page intentionally references the Electron app's onboarding direction, brand language, and desktop control-plane concept while keeping the CLI install and testing path separate.

## Core Features

### Hypothesis-Tree Research

DevPilot represents work as a tree of ideas. The Coordinator proposes hypotheses, selects promising branches, sends them to Executors, and records outcomes. Failed paths are kept as evidence instead of disappearing.

### Coordinator And Executor Agents

- **Coordinator**: plans the search, maintains the idea tree, decides what to test next.
- **Executor**: implements one hypothesis, runs commands, gathers evidence, and reports back.

### Local Learning Layer

Learning data is stored under the active project:

```text
.devpilot/
  memory/
    memories.jsonl
    skills.jsonl
    trajectories.jsonl
  sessions/
```

Learning commands:

```powershell
devpilot learn doctor
devpilot learn summarize
devpilot learn memory list
devpilot learn memory search "query"
devpilot learn skills list
devpilot learn skills mine
devpilot learn trajectory compress
```

Phase 1 learning is deterministic and local. It does not require background jobs, messaging gateways, browser automation, or cloud runners.

### Reach, Memory, Compression, And Audit Extensions

The CLI also includes optional command groups for:

- `devpilot reach`: safe local research channels and evidence persistence.
- `devpilot memory`: optional MemPalace-backed semantic memory.
- `devpilot compress`: optional Headroom-backed context compression.
- `devpilot audit`: local AI safety audit wrapper.
- `devpilot skills`: built-in reusable coding playbooks.

These are optional layers around the core local DevPilot runtime.

## Supported Platforms

Tested target environment for this submission:

- Windows PowerShell
- Python 3.10+
- Git

The code is Python-first and should also work on macOS/Linux with the usual shell changes, but the judge quickstart below is written for Windows because that is the primary development environment used for this submission.

## Installation

Clone the repository:

```powershell
git clone https://github.com/mylife-as-miles/DevPilot-CLI.git
cd DevPilot-CLI
```

Create and activate a virtual environment:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the CLI locally:

```powershell
pip install -e .
```

Configure DevPilot:

```powershell
devpilot setup
devpilot setup
```

The setup wizard configures provider, model, API key or OAuth flow, and reasoning effort. For a full model-powered run, judges should use their own OpenAI/Codex credentials.

## Run DevPilot On Another Project

Use `--cwd` to point DevPilot at the project you want it to inspect or improve:

```powershell
devpilot --cwd C:\path\to\another-project
```

Example:

```powershell
devpilot --cwd C:\Users\MILES\Documents\Jobraker-Recruiter
```

DevPilot will start its intake flow and ask for the goal, constraints, evaluation command, and budget before launching a research run.

## Judge Smoke Tests

These commands are intended to work gracefully even before running a long autonomous session:

```powershell
devpilot --help
devpilot setup --help
devpilot doctor
devpilot learn doctor
devpilot learn summarize
devpilot learn memory list
devpilot learn memory search "query"
devpilot learn skills list
devpilot learn trajectory compress
```

Optional test suite:

```powershell
pytest
```

If no previous `.devpilot/` session exists in the current project, learning commands should show useful empty states instead of crashing.

## Minimal Demo Flow

For a short local demo:

1. Install the CLI.
2. Run `devpilot setup`.
3. Move to or point at any local git project.
4. Run `devpilot --cwd C:\path\to\project`.
5. In the intake flow, provide a small bounded goal, such as "inspect the repository and propose one safe improvement."
6. Review the generated session artifacts under `.devpilot/sessions/`.
7. Run `devpilot learn summarize` or `devpilot learn trajectory compress`.

## Configuration Notes

DevPilot supports multiple provider paths, including OpenAI Responses, OpenAI-compatible chat endpoints, LiteLLM, Gemini, Anthropic, and ChatGPT OAuth flows where configured.

For Build Week, the setup path was adjusted around GPT-5.6 model choices:

- `gpt-5.6-sol`
- `gpt-5.6-terra`
- `gpt-5.6-luna`

The CLI keeps provider configuration outside project code. Project-local run state lives under `.devpilot/`.

## Project Structure

```text
src/
  cli/                  Typer CLI and command groups
  coordinator/          hypothesis-tree planning agent
  executor/             isolated executor agent
  core/
    learning/           memory, skill mining, trajectory compression
    llm/                provider adapters
    tools/              runtime tools
  report/               report generation
  skills/               built-in playbooks
tests/                  regression tests
docs/                   usage documentation
examples/               small benchmark examples
sites/devpilot-cli-landing/
                        Build Week landing page source
```

The companion Electron app source is maintained in the separate `mylife-as-miles/DevPilot` repository, not vendored into this CLI package.

## What To Look At In The Code

Useful entry points:

- `src/cli/app.py`: top-level CLI registration.
- `src/cli/commands/setup_cmd.py`: model/provider setup flow.
- `src/cli/commands/learn_cmd.py`: learning CLI commands.
- `src/core/learning/`: local memory, skills, search, and trajectory compression.
- `src/coordinator/`: hypothesis-tree orchestration.
- `src/executor/`: executor loop.
- `src/report/`: session report generation.

## Devpost Submission Notes

Recommended category: **Developer Tools**.

No shared credentials are required for basic CLI smoke tests. For full autonomous runs, judges should configure their own provider credentials with `devpilot setup`.

If the repository is private during judging, it must be shared with:

- `testing@devpost.com`
- `build-week-event@openai.com`

The `/feedback` Codex session ID should be added in the Devpost form, not hard-coded in this README.

## Safety Model

The learning layer is intentionally conservative:

- No global learning store in Phase 1.
- No background jobs.
- No messaging gateways.
- No browser automation.
- No remote/cloud runners.
- No automatic edits outside DevPilot's `.devpilot/` workspace unless the user launches an explicit run.
- JSONL memory files are append-only and human-readable.

Executor work is designed to be reviewable through git branches, reports, and local artifacts.

## License

DevPilot CLI is released under the [Apache License 2.0](LICENSE).

Some optional vendored or referenced upstream projects have their own licenses. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution.
