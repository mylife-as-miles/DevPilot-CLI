<p align="center">
  <img src="assets/hero.svg" alt="DevPilot" width="100%">
</p>

<h1 align="center">DevPilot</h1>

<p align="center">
  <strong>Autonomous research for your codebase -- driven by the Idea Tree.</strong><br>
  Describe a goal — DevPilot proposes ideas, runs experiments, and keeps what improves your metric.
</p>

<p align="center">
  <a href="https://arxiv.org/pdf/2606.11926">Paper</a> ·
  <a href="https://github.com/mylife-as-miles/DevPilot-CLI">Repository</a> ·
  <a href="docs/index.md">Documentation</a> ·
  <a href="LICENSE">License</a>
</p>

<p align="center">
  <a href="https://github.com/mylife-as-miles/DevPilot-CLI/actions"><img src="https://img.shields.io/badge/Python-3.10%2B-blue" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-green" alt="Apache 2.0"></a>
</p>

---

## Overview

DevPilot is an autonomous research agent that turns a long-horizon objective into a cumulative search. Give it a benchmark and a goal; it proposes hypotheses, edits code, runs real experiments, learns from the results, and keeps improvements that hold up on held-out data.

Instead of one-shot attempts that forget what failed, DevPilot grows a **hypothesis tree**: every idea becomes a branch — pruned if it fails, harvested if it works — and insights propagate so later ideas start smarter.

This repository is a maintained CLI distribution of [DevPilot](https://github.com/RUC-NLPIR/DevPilot), published as **`miles-devpilot-cli`**. It adds first-class support for **Google Gemini** via the Interactions API, OpenAI OAuth login, GitLab Orbit knowledge-graph context, and the existing Anthropic, OpenAI, and OpenAI-compatible backends.

## Features

- **Hypothesis-tree exploration** — Structured, long-horizon search with persistent insights across cycles.
- **Real experiment discipline** — Executors iterate on a dev split, validate on a held-out test split, and only merge gains above a configurable margin.
- **Isolated execution** — Each experiment runs in its own git worktree on a dedicated branch; `main` stays untouched until you choose to merge.
- **Interactive intake** — A conversational setup phase turns your goal, metric, baseline, and constraints into a one-screen Research Contract before the run starts.
- **Live observability** — Terminal dashboard, optional read-only WebUI, slash commands, and checkpoint/resume for long runs.
- **Flexible LLM backends** — Anthropic Claude, OpenAI Responses API, Gemini (Interactions API), OpenAI-compatible gateways (DeepSeek, Qwen, vLLM, Ollama), and LiteLLM.
- **GitLab Orbit context** — Optional Orbit Local/Remote knowledge-graph discovery before experiments run.
- **DevPilot Learning Layer** — Project-local memories, trajectory compression, and reusable skill mining from past runs.
- **MemPalace long-term memory** — Optional semantic recall over DevPilot sessions, Reach evidence, and learned JSONL artifacts.
- **Headroom compression** — Optional context compression for large evidence, memory, logs, and session artifacts.
- **Domain plugins** — Retarget evaluation rules, protected paths, and budgets with a single YAML plugin line.
- **Agent Skill Suite** — Optional Codex / Claude Code skills for DevPilot-style workflows outside the native runtime.

## Architecture

<p align="center">
  <img src="assets/framework.png" alt="DevPilot architecture" width="90%">
</p>

DevPilot runs two cooperating agents:

| Agent | Role |
| --- | --- |
| **Coordinator** | Research director. Maintains the Idea Tree, drives the search cycle, and dispatches experiments. |
| **Executor** | Research engineer. Implements one idea in an isolated worktree, runs evaluation, and reports evidence. |

Each **DevPilot cycle** follows six steps:

1. **Observe** — Re-ground in the Idea Tree: frontier, constraints, ancestor insights, and recent evidence.
2. **Ideate** — Propose child hypotheses that refine or extend what the tree has learned.
3. **Select** — Choose the most promising pending leaves to test next.
4. **Dispatch** — Send selected hypotheses to independent Executors.
5. **Backpropagate** — Record results, scores, and insights; abstract lessons upward.
6. **Decide** — Merge, prune, continue, or stop based on held-out validation.

## Installation

**Requirements:** Python 3.10 or newer, Git, and an LLM API key.

### From PyPI

```bash
pip install miles-devpilot-cli
devpilot doctor
```

For an isolated global install:

```bash
pipx install miles-devpilot-cli
```

### From source

```bash
git clone https://github.com/mylife-as-miles/DevPilot-CLI.git
cd DevPilot-CLI
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.\.venv\Scripts\Activate.ps1

pip install -e .
devpilot doctor
```

## Quick start

### 1. Configure your model

Run the setup wizard once. Settings are stored in `~/.devpilot/config.yaml`.

```bash
devpilot setup
```

You will be prompted for provider, model, base URL (if any), API key, and reasoning effort.

### 2. Start a session

```bash
cd your-benchmark-directory
devpilot
```

DevPilot opens an **intake conversation** to confirm your target directory, metric, baseline, budget, and evaluation discipline. When you approve the Research Contract, the coordinator launches and the live dashboard takes over.

### 3. Run with options

```bash
# Point at a specific directory and config
devpilot --cwd ./benchmark --config research_config.yaml

# Seed the goal up front; intake refines the rest
devpilot "improve validation score without touching the test split" --cwd ./benchmark

# Limit exploration depth for a dry run
devpilot --cwd ./benchmark --config research_config.yaml --max-cycles 3
```

### In-session commands

During a run, type slash commands such as `/status`, `/tree`, `/evidence`, `/branches`, `/cost`, `/pause`, `/resume`, `/report`, or `/abort`.

## Preparing a benchmark

Your target directory should include:

- A runnable evaluation script (for example `run_eval.py`)
- Evaluation data with a **dev** split and a held-out **test** split
- A clean git repository (no uncommitted changes)

Minimal project config:

```yaml
task: >
  Optimize the agent's accuracy on the benchmark.
  Do NOT modify the evaluation harness or data files.

coordinator:
  max_cycles: 10
  max_depth: 2
  merge_threshold: 5.0
  ui:
    interaction_mode: review   # auto | direction | review | collaborative

executor:
  max_turns: 100
```

See [`examples/research_config.example.yaml`](examples/research_config.example.yaml) for a full reference.

### Example: AlgoTune k-NN

[`examples/algotune_knn/`](examples/algotune_knn) is a self-contained CPU-only benchmark: make a brute-force k-nearest-neighbours solver faster while matching the reference output. No GPU required; runs complete in seconds.

```bash
cp -r examples/algotune_knn /tmp/algotune_knn
cd /tmp/algotune_knn
git init -q && git add -A && git commit -qm baseline
devpilot
```

Run this **outside** your DevPilot checkout so experiment worktrees do not modify the source repo.

## Configuration

### LLM providers

Global LLM settings live in `~/.devpilot/config.yaml` (written by `devpilot setup`). Per-project task and budget settings belong in a project config file.

| Provider | Description |
| --- | --- |
| `auto` | Detect the best backend for your model and endpoint. |
| `anthropic` | Claude via the native Anthropic Messages API. |
| `openai-responses` | OpenAI / o-series via the Responses API (reasoning chain preserved). |
| `openai-chat` | Any OpenAI-compatible chat-completions endpoint. |
| `openai-oauth` | ChatGPT subscription via browser login (experimental). |
| `gemini` | Gemini via the Google Interactions API (`thinking_level` + function calling). |

Set API keys in the config file or via environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` / `GOOGLE_API_KEY`).

```bash
devpilot config show          # view current settings
devpilot config init --force  # non-interactive reconfiguration
```

### Interaction modes

| Mode | Behavior |
| --- | --- |
| `auto` | Fully autonomous. |
| `direction` | Asks where to go next at ideation. |
| `review` | Pauses before each node and Executor. |
| `collaborative` | Combines direction and review. |

Set via `ui.interaction_mode` in your project config or the appropriate CLI flag.

### GitLab Orbit

DevPilot can use GitLab Orbit as an optional knowledge-graph discovery step before launching Executors. Orbit is useful for questions like "what depends on this file?", "which services call this symbol?", "which merge requests touched this area?", and "what pipelines or security findings are connected to this change?"

Enable Orbit Local in `devpilot.yaml` or `research_config.yaml` after indexing the repository:

```yaml
orbit:
  enabled: true
  mode: local
  command: orbit
  database_path: ~/.orbit/graph.duckdb
```

Make it required for GitLab-backed runs:

```yaml
orbit:
  enabled: true
  mode: local
  required: true
```

See [GitLab Orbit](docs/orbit.md) for Local and Remote setup.

## CLI reference

| Command | Description |
| --- | --- |
| `devpilot` | Start an interactive research session (intake + run). |
| `devpilot setup` | Configure provider, model, and API keys. |
| `devpilot doctor` | Diagnose install, PATH, git, and API connectivity. |
| `devpilot config` | View or edit global configuration. |
| `devpilot report <session>` | Re-render `REPORT.md` for a past session. |
| `devpilot learn` | Inspect local run memories, mined skills, and compressed trajectories. |
| `devpilot memory` | Index and search DevPilot artifacts with optional MemPalace recall. |
| `devpilot compress` | Compress large session, evidence, log, and prompt context with optional Headroom support. |
| `devpilot audit` | Run local iFixAi AI safety audits through DevPilot. |
| `devpilot skills` | List and inspect built-in DevPilot prompt skills. |
| `devpilot export <session>` | Export a session to HTML or JSONL. |
| `devpilot version` | Print the installed version. |

Lower-level entry points (`run-research`, `coordinator`, `executor`, `review-research`) are available for advanced workflows.

## Outputs and resume

Each run writes a session directory under `.devpilot/sessions/` containing:

- `REPORT.md` — final research report
- Idea Tree state and conversation history
- `events.jsonl` and `run_stats.json`
- Per-experiment artifacts

Interrupted runs can be resumed:

```bash
devpilot --resume --run-name <run_name>
```

## DevPilot Reach

DevPilot Reach is an optional internet research capability layer. It provides safe no-login channels natively and can bridge to [Agent Reach](https://github.com/Panniantong/agent-reach) when installed.

**Phase 1** supports web, search, GitHub, YouTube, and RSS channels. Cookie/login platforms (Twitter, Reddit, Instagram, etc.) are not implemented in Phase 1.

```bash
# Diagnostics
devpilot reach doctor
devpilot reach providers

# Native channels
devpilot reach visit https://example.com --max-chars 6000
devpilot reach search "transformer architecture"
devpilot reach github repo openai/openai-python
devpilot reach youtube "https://youtube.com/watch?v=..."
devpilot reach rss https://hnrss.org/frontpage

# Agent Reach bridge (optional)
devpilot reach agent-reach status
devpilot reach agent-reach doctor
devpilot reach agent-reach install-help
devpilot reach agent-reach update-help
```

**Agent Reach** can be installed separately.  OpenClaw users need exec/coding permissions before asking OpenClaw to install Agent Reach — run `devpilot reach agent-reach install-help` for details.

**Runtime integration**: Reach channels are also exposed as read-only agent tools (`reach_search`, `reach_visit`, `reach_github_repo`, `reach_youtube_transcript`, `reach_rss_read`) so the Coordinator and Executor can call them during autonomous research runs.  These tools are registered automatically and gracefully handle missing optional dependencies.

**Evidence Store**: When Reach tools are called within an active research session, their outputs are persisted as structured evidence in a JSONL file (`reach_evidence.jsonl`) under the active run's session directory (e.g. `<session_dir>/reach_evidence.jsonl`). Each record contains:
*   Tool name, query/input, and source URL or identifier
*   Retrieved timestamp, content/excerpt, and page title (if available)
*   Attributed `cycle_id` and `hypothesis_id` (idea ID) if called from a runtime executor context

This evidence store serves as a structured, read-only reference of all internet research performed during the lifetime of a research run. If run outside of a session context (e.g. via direct CLI commands), the tools bypass evidence persistence.

## DevPilot Learning Layer

DevPilot can now learn from previous runs by extracting local memories, compressing trajectories, and mining reusable skills.

Learning data is stored under the active project in `.devpilot/memory/` as append-only JSONL. Phase 1 is local and deterministic: no network calls, no background jobs, no messaging gateways, and no global learning store.

```bash
devpilot learn doctor
devpilot learn summarize
devpilot learn memory search "query"
devpilot learn skills mine
devpilot learn trajectory compress
```

The learning layer is inspired by self-improving agent systems like [Hermes Agent](https://github.com/NousResearch/hermes-agent), but it is implemented natively for DevPilot. Coordinator and Executor prompts receive only a small learned-memory section: at most five relevant memories and three reusable skills.

## DevPilot Memory with MemPalace

DevPilot can use [MemPalace](https://github.com/MemPalace/mempalace) as an optional long-term semantic memory engine. MemPalace is vendored as upstream MIT software under `vendor/mempalace`; DevPilot wraps its CLI instead of rewriting it, and core DevPilot does not require MemPalace dependencies.

```bash
git submodule update --init --recursive
devpilot memory doctor
devpilot memory install --dry-run
devpilot memory init
devpilot memory sync-evidence
devpilot memory mine --all
devpilot memory search "why did we change the evaluator?"
devpilot memory wake-up
```

DevPilot keeps its own memory metadata under the active project in `.devpilot/memory/`. MemPalace indexes local exports of sessions, Reach evidence, reports, learned memories, skills, and trajectories. MemPalace stores verbatim text locally by default; external backends such as Qdrant or pgvector are opt-in and may store verbatim data outside the machine.

Prompt recall is opt-in for Phase 1:

```yaml
memory:
  provider: mempalace
  enabled: false
  auto_wake_up: false
  max_context_chars: 4000
```

## DevPilot Compression with Headroom

DevPilot can optionally use [Headroom](https://github.com/headroomlabs-ai/headroom) as a context-compression layer for large evidence, memory, logs, and session artifacts. Headroom is vendored as upstream Apache-2.0 software under `vendor/headroom`; DevPilot wraps it instead of rewriting it, and core DevPilot does not require Headroom dependencies.

```bash
git submodule update --init --recursive
devpilot compress doctor
devpilot compress install --dry-run
devpilot compress text README.md
devpilot compress evidence
devpilot compress session
devpilot compress proxy-help
```

Compression is optional and should preserve source traceability: source URLs, hypothesis IDs, failing test names, and key decisions are kept in the compressed output. Runtime prompt compression is off by default:

```yaml
compression:
  provider: headroom
  enabled: false
  compress_reach_evidence: true
  compress_memory_context: true
  compress_test_logs: true
  max_context_chars: 6000
```

## DevPilot Audit Layer

DevPilot can run local AI safety audits through a native wrapper around the upstream [iFixAi](https://github.com/ifixai-ai/iFixAi) project. iFixAi is kept as exact upstream source under `vendor/iFixAi`; DevPilot does not modify it or store provider API keys.

Phase 1 is local and explicit: audit output is written under `.devpilot/audit/`, mock runs are safe by default, and non-mock providers require confirmation plus an API key supplied through an environment variable.

```bash
devpilot audit doctor
devpilot audit install --dry-run
devpilot audit run --provider mock --suite smoke
devpilot audit run --suite core
devpilot audit setup
devpilot audit report
devpilot audit ifixai --help
```

The audit layer is inspired by iFixAi's diagnostic approach, but the DevPilot integration is implemented natively as a safe local CLI bridge.

## Built-in Coding Discipline Skill

DevPilot includes a Karpathy-inspired coding guideline skill for careful, simple, surgical, test-driven code edits.

```bash
devpilot skills list
devpilot skills show karpathy-coding
```

The skill is adapted from [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) and packaged natively as a DevPilot skill, not as a runtime dependency.

## CLI vs. Agent Skills

| | Native CLI | Agent Skill Suite |
| --- | --- | --- |
| **Location** | `devpilot` command | [`skills/`](skills/README.md) |
| **Best for** | Full research runs, dashboard, checkpoints, merge discipline | Gitlab Duo Agent / Codex / Claude Code environments |
| **Recommendation** | Preferred for complete DevPilot behavior | Useful integration layer |

## Project structure

```
src/                    # imported as the `devpilot` package
├── core/               # ReAct loop, LLM providers, tools, context management
│   └── learning/       # Local memory, skill mining, and trajectory compression
├── coordinator/        # Idea Tree, orchestrator, coordinator tools
├── executor/           # Executor agent and CLI
├── cli/                # Interactive CLI, intake, setup, dashboard
├── events/             # Typed event bus
├── report/             # Report generation
├── webui/              # Read-only monitoring server
├── plugins/            # Domain plugins
└── skills/             # On-demand markdown playbooks
```

Optional upstream integrations are kept under `vendor/`, including Hermes Agent at `vendor/hermes-agent`, Headroom at `vendor/headroom`, and the MemPalace submodule at `vendor/mempalace`.

## Documentation

Detailed guides are available in [`docs/`](docs/index.md):

- [Quickstart](docs/quickstart.md)
- [Configuration](docs/configuration.md)
- [Preparing a benchmark](docs/preparing-a-benchmark.md)
- [Interaction modes](docs/interaction-modes.md)
- [GitLab Orbit](docs/orbit.md)
- [Outputs and resume](docs/outputs-and-resume.md)
- [Plugins](docs/plugins.md)

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions and guidelines.

- [Discussions](https://github.com/RUC-NLPIR/DevPilot/discussions) — questions and ideas
- [Issues](https://github.com/mylife-as-miles/DevPilot-CLI/issues) — bugs and feature requests for this fork

## License

Released under the [Apache License 2.0](LICENSE).
