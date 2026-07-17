<p align="center">
  <img src="assets/hero.svg" alt="DevPilot" width="100%">
</p>

<h1 align="center">DevPilot</h1>

<p align="center">
  <strong>Autonomous research for your codebase.</strong><br>
  Describe a goal — DevPilot proposes ideas, runs experiments, and keeps what improves your metric.
</p>

<p align="center">
  <a href="https://arxiv.org/pdf/2606.11926">Paper</a> ·
  <a href="https://RUC-NLPIR.github.io/DevPilot/">Project page</a> ·
  <a href="https://RUC-NLPIR.github.io/DevPilot/docs/">Documentation</a> ·
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

This repository is a maintained CLI distribution of [DevPilot](https://github.com/RUC-NLPIR/DevPilot), with first-class support for **Google Gemini** via the Interactions API, alongside Anthropic, OpenAI, and OpenAI-compatible backends.

## Features

- **Hypothesis-tree exploration** — Structured, long-horizon search with persistent insights across cycles.
- **Real experiment discipline** — Executors iterate on a dev split, validate on a held-out test split, and only merge gains above a configurable margin.
- **Isolated execution** — Each experiment runs in its own git worktree on a dedicated branch; `main` stays untouched until you choose to merge.
- **Interactive intake** — A conversational setup phase turns your goal, metric, baseline, and constraints into a one-screen Research Contract before the run starts.
- **Live observability** — Terminal dashboard, optional read-only WebUI, slash commands, and checkpoint/resume for long runs.
- **Flexible LLM backends** — Anthropic Claude, OpenAI Responses API, Gemini (Interactions API), OpenAI-compatible gateways (DeepSeek, Qwen, vLLM, Ollama), and LiteLLM.
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
pip install devpilot-agent
devpilot doctor
```

For an isolated global install:

```bash
pipx install devpilot-agent
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

## CLI reference

| Command | Description |
| --- | --- |
| `devpilot` | Start an interactive research session (intake + run). |
| `devpilot setup` | Configure provider, model, and API keys. |
| `devpilot doctor` | Diagnose install, PATH, git, and API connectivity. |
| `devpilot config` | View or edit global configuration. |
| `devpilot report <session>` | Re-render `REPORT.md` for a past session. |
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

## CLI vs. Agent Skills

| | Native CLI | Agent Skill Suite |
| --- | --- | --- |
| **Location** | `devpilot` command | [`skills/`](skills/README.md) |
| **Best for** | Full research runs, dashboard, checkpoints, merge discipline | Codex / Claude Code environments |
| **Recommendation** | Preferred for complete DevPilot behavior | Useful integration layer |

## Project structure

```
src/                    # imported as the `devpilot` package
├── core/               # ReAct loop, LLM providers, tools, context management
├── coordinator/        # Idea Tree, orchestrator, coordinator tools
├── executor/           # Executor agent and CLI
├── cli/                # Interactive CLI, intake, setup, dashboard
├── events/             # Typed event bus
├── report/             # Report generation
├── webui/              # Read-only monitoring server
├── plugins/            # Domain plugins
└── skills/             # On-demand markdown playbooks
```

## Documentation

Detailed guides are available in [`docs/`](docs/index.md) and on the [project documentation site](https://RUC-NLPIR.github.io/DevPilot/docs/):

- [Quickstart](docs/quickstart.md)
- [Configuration](docs/configuration.md)
- [Preparing a benchmark](docs/preparing-a-benchmark.md)
- [Interaction modes](docs/interaction-modes.md)
- [Outputs and resume](docs/outputs-and-resume.md)
- [Plugins](docs/plugins.md)

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup instructions and guidelines.

- [Discussions](https://github.com/RUC-NLPIR/DevPilot/discussions) — questions and ideas
- [Issues](https://github.com/mylife-as-miles/DevPilot-CLI/issues) — bugs and feature requests for this fork

## License

Released under the [Apache License 2.0](LICENSE).

## Acknowledgments

DevPilot is based on research from Renmin University of China ([paper](https://arxiv.org/pdf/2606.11926), [upstream repository](https://github.com/RUC-NLPIR/DevPilot)).

Maintained by [Osita Miles](https://github.com/mylife-as-miles).
