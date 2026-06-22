# DevPilot Research Agent Skill Suite

This directory contains a Codex/Claude Code skill suite that reconstructs the
open-source DevPilot/AutoResearch behavior from `devpilot` as a set of
Agent Skills.

Most users should invoke only the public entrypoint:

```text
$devpilot-research-agent <your research or optimization request>
```

In Claude Code, the equivalent direct invocation is usually:

```text
/devpilot-research-agent <your research or optimization request>
```

The internal phase skills are still required. Install all `devpilot-*` skill
directories together; do not install only `devpilot-research-agent`.

## Quick Download And Installation

Set `REPO_URL` to the DevPilot GitHub repository and `REPO_REF` to the branch or
tag that contains this `skills/` directory.

```bash
REPO_URL="https://github.com/RUC-NLPIR/DevPilot.git"
REPO_REF="main"
TMP_DIR="$(mktemp -d)"
git clone --depth 1 --branch "$REPO_REF" "$REPO_URL" "$TMP_DIR/devpilot-skill-suite"
SKILLS_SRC="$TMP_DIR/devpilot-skill-suite/skills"
```

If you are installing from the current local checkout instead of GitHub, use:

```bash
SKILLS_SRC="<path-to-DevPilot>/skills"
```

### Install into Codex

```bash
CODEX_SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$CODEX_SKILLS_DIR"
cp -R "$SKILLS_SRC"/devpilot-* "$CODEX_SKILLS_DIR"/
find "$CODEX_SKILLS_DIR" -maxdepth 1 -type d -name 'devpilot-*' | sort
```

Restart Codex after installation. Then invoke:

```text
$devpilot-research-agent <your task>
```

### Install into Claude Code

User-level installation:

```bash
mkdir -p ~/.claude/skills
cp -R "$SKILLS_SRC"/devpilot-* ~/.claude/skills/
find ~/.claude/skills -maxdepth 1 -type d -name 'devpilot-*' | sort
```

Project-level installation:

```bash
mkdir -p <target_repo>/.claude/skills
cp -R "$SKILLS_SRC"/devpilot-* <target_repo>/.claude/skills/
find <target_repo>/.claude/skills -maxdepth 1 -type d -name 'devpilot-*' | sort
```

Restart Claude Code after installation. Then invoke:

```text
/devpilot-research-agent <your task>
```

### Let Codex Install It

Paste this prompt into Codex:

```text
Install the DevPilot Research Agent skill suite from
https://github.com/RUC-NLPIR/DevPilot.git, branch main. Clone the repo
into a temporary directory, locate skills/devpilot-research-agent/SKILL.md, and
copy every skills/devpilot-* directory into ${CODEX_HOME:-$HOME/.codex}/skills. Do
not copy only the wrapper skill. Do not modify the target project source. After
copying, verify that 11 devpilot-* skill directories exist and that each contains
SKILL.md. Then tell me to restart Codex and show the exact path you installed
to.
```

For local installation from this checkout, use:

```text
Install the DevPilot Research Agent skill suite from <path-to-DevPilot>/skills.
Copy every devpilot-* directory into ${CODEX_HOME:-$HOME/.codex}/skills. Do not
copy only the wrapper skill. Verify that 11 devpilot-* skill directories exist and
that each contains SKILL.md. Then tell me to restart Codex and show the exact
path you installed to.
```

### Let Claude Code Install It

Paste this prompt into Claude Code:

```text
Install the DevPilot Research Agent skill suite from
https://github.com/RUC-NLPIR/DevPilot.git, branch main. Clone the repo
into a temporary directory, locate skills/devpilot-research-agent/SKILL.md, and
copy every skills/devpilot-* directory into ~/.claude/skills. Do not copy only the
wrapper skill. Do not modify the target project source. After copying, verify
that 11 devpilot-* skill directories exist and that each contains SKILL.md. Then
tell me to restart Claude Code and show the exact path you installed to.
```

For project-level installation, use this prompt instead:

```text
Install the DevPilot Research Agent skill suite from
https://github.com/RUC-NLPIR/DevPilot.git, branch main, into this
project's .claude/skills directory. Clone the repo into a temporary directory,
locate skills/devpilot-research-agent/SKILL.md, and copy every skills/devpilot-*
directory into .claude/skills. Do not copy only the wrapper skill. Do not modify
source files outside .claude/skills. Verify that 11 devpilot-* skill directories
exist and that each contains SKILL.md. Then tell me to restart Claude Code.
```

## Status

The suite is usable and aligns with DevPilot's core behavior at the level that
Agent Skills can express and execute.

It covers:

- A public intake entrypoint similar to `devpilot run`.
- An DevPilot-style clarification checkpoint for missing target, metric, data,
  evaluation, permissions, budget, and run mode.
- Fast-path execution when the user already provides enough constraints or
  explicitly says to use safe defaults.
- A research contract passed from the public wrapper into the orchestrator.
- A phase-loading orchestrator rather than one monolithic skill.
- Durable `.devpilot/sessions/<run_name>/` session state.
- An Idea Tree as persistent memory across context changes.
- B_dev/B_test discipline: B_dev for iteration, B_test only for merge/final
  verification.
- Coordinator discipline: the coordinator does not directly edit benchmark or
  project source code; implementation work goes through executor/worktree
  behavior.
- IDEATE, executor, merge/eval, related-work search, plugin/HITL/budget,
  resume, and report behavior.
- A deterministic fallback helper, `devpilot_state.py`, for Codex/Claude
  environments without native DevPilot tools.

Important boundary: this is not a binary replacement for the native `devpilot`
CLI runtime. Native dashboard rendering, EventBus streaming, provider runtime,
full native executor concurrency, and the background SearchAgent lifecycle
still belong to the original DevPilot runtime. If the native `devpilot` CLI is
installed and the goal is a production DevPilot run, prefer the native runtime.
This skill suite is intended to make Codex or Claude Code behave according to
the DevPilot design when native DevPilot tools are unavailable or when a
skill-based reconstruction is desired.

## Skill Layout

Install these 11 skill directories as a single suite:

| Skill | Responsibility |
| --- | --- |
| `devpilot-research-agent` | Public entrypoint. Performs DevPilot-style intake/clarification, forms the research contract, then loads the orchestrator. |
| `devpilot-agent-orchestrator` | Top-level phase loader and policy owner. Decides when to load each phase skill. |
| `devpilot-agent-setup-intake` | Project intake, metric/eval discovery, baseline handling, B_dev/B_test policy, and session setup. |
| `devpilot-agent-coordinator` | INIT/OBSERVE/IDEATE/SELECT/DISPATCH/DECIDE loop and durable Idea Tree operation. |
| `devpilot-agent-ideate` | Reconstructs idea drafting and first-principles probing. Enforces constraints view and four-line hypotheses. |
| `devpilot-agent-executor` | Executor/worktree/prompt/report/metrics/insight-propagation behavior. |
| `devpilot-agent-merge-eval` | B_dev/B_test separation, merge guards, protected paths, metric direction, and final scoring. |
| `devpilot-agent-search` | Related-work and novelty search for validated winners. |
| `devpilot-agent-plugins-hitl-budget` | Plugin/profile precedence, MLE/Kaggle behavior, HITL gates, and budget/cycle policy. |
| `devpilot-agent-resume-report` | Checkpoint/resume behavior, running-node requeue, and `REPORT.md` finalization. |
| `devpilot-agent-tools` | Deterministic fallback tools for environments without native DevPilot tools. |

Each skill directory contains:

- `SKILL.md`: the cross-platform instruction body used by Codex and Claude
  Code.
- `agents/openai.yaml`: OpenAI/Codex UI metadata. This file controls display
  name, short description, and default prompt text. It does not contain the
  execution logic.

Additional resources:

- `devpilot-agent-orchestrator/references/source-map.md`: source-level mapping
  from the `devpilot` open-source branch to this suite.
- `devpilot-agent-orchestrator/references/compatibility.md`: Codex and Claude
  Code compatibility notes.
- `devpilot-agent-tools/references/tool-mapping.md`: mapping between native DevPilot
  tools and fallback helper commands.
- `devpilot-agent-tools/scripts/devpilot_state.py`: a stdlib-only helper that
  supports `init`, `view`, `meta`, `add`, `update`, `prune`, `propagate`,
  `eval`, `parse-log`, `prompt-executor`, `record`, `worktree`, `merge`,
  `check`, and `report`.

## DevPilot Behavior Mapping

| DevPilot behavior | Skill suite equivalent |
| --- | --- |
| `devpilot run` starts with intake and a Research Contract | `devpilot-research-agent` |
| `.devpilot/sessions/<run_name>/` session layout | `devpilot-agent-setup-intake` + `devpilot-agent-tools` |
| Persistent coordinator ReAct loop | `devpilot-agent-orchestrator` + `devpilot-agent-coordinator` |
| `TreeView`, `TreeAddNode`, `TreeSetMeta`, `TreeUpdateNode`, `TreePropagate` | `devpilot-agent-coordinator` + `devpilot_state.py` |
| `TreeView(format="constraints")` before ideation | `devpilot-agent-ideate` |
| Four-line hypothesis: `Mechanism`, `Hypothesis`, `Observable`, `Conflicts` | `devpilot-agent-ideate` |
| `RunExecutor` / `RunExecutorParallel` | `devpilot-agent-executor` |
| Executor evaluates on B_dev and avoids B_test | `devpilot-agent-executor` + `devpilot-agent-merge-eval` |
| `GitMergeBranch` auto-runs B_test verification and protected-path checks | `devpilot-agent-merge-eval` + `devpilot_state.py merge` |
| SearchAgent annotates validated winners only | `devpilot-agent-search` |
| Plugin/profile/HITL/budget policy | `devpilot-agent-plugins-hitl-budget` |
| Checkpoint/resume/final report | `devpilot-agent-resume-report` + `devpilot_state.py report` |
| Long training and noisy progress logs | `devpilot-agent-executor` + `devpilot_state.py parse-log` |

## Loading In Codex

### Recommended installation

Codex installs skills into `${CODEX_HOME:-$HOME/.codex}/skills` by default.
From this repository, install the whole suite with:

```bash
CODEX_SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$CODEX_SKILLS_DIR"
cp -R <path-to-DevPilot>/skills/devpilot-* "$CODEX_SKILLS_DIR"/
```

Restart Codex after copying the skills.

Then open Codex in the target project and invoke the public entrypoint:

```text
$devpilot-research-agent optimize this repo for the leaderboard metric. Ask before training, installing packages, or using B_test.
```

For a smoke test:

```text
$devpilot-research-agent try a one-cycle smoke run in this repo. Do not edit source, do not train, use cached metrics where safe, and write an DevPilot-style report.
```

### One-off forward test

For a temporary test without installing the suite globally, expose this
repository to Codex and explicitly tell the agent to start from the public
entrypoint:

```bash
codex exec --add-dir <path-to-DevPilot> -C <target_repo> \
  'Use the skill suite under <path-to-DevPilot>/skills. Start from devpilot-research-agent. <your task>'
```

This is useful for validation. For normal use, install the skills into the
Codex skills directory.

## Loading In Claude Code

Claude Code skills are directories that contain a `SKILL.md` file. Official
Claude Code documentation describes both project skills under
`.claude/skills/*/SKILL.md` and user skills under `~/.claude/skills/`. Direct
skill invocation uses `/skill-name`.

Reference: <https://code.claude.com/docs/en/skills>

### User-level installation

Use this when you want the suite available across multiple projects:

```bash
mkdir -p ~/.claude/skills
cp -R <path-to-DevPilot>/skills/devpilot-* ~/.claude/skills/
```

Restart Claude Code, open the target project, and invoke:

```text
/devpilot-research-agent optimize this repo for the validation score. Ask before running training or editing protected files.
```

### Project-level installation

Use this when you want the suite attached to one repository:

```bash
mkdir -p <target_repo>/.claude/skills
cp -R <path-to-DevPilot>/skills/devpilot-* <target_repo>/.claude/skills/
```

Then start Claude Code inside `<target_repo>` and invoke:

```text
/devpilot-research-agent try a smoke-only DevPilot run. Use current cwd, no training, no source edits, one cycle, write REPORT.md.
```

If Claude Code does not auto-trigger the skill, explicitly ask it to read the
public entrypoint:

```text
Read .claude/skills/devpilot-research-agent/SKILL.md and follow it as the public entrypoint. Then handle: <your task>
```

## Usage After Loading

### Real run

Codex:

```text
$devpilot-research-agent optimize this repo for <metric>. You may edit source through executor branches, run <eval command> on B_dev, and stop after 5 cycles or 4 hours. Ask before package installs, data downloads, GPU jobs longer than 30 minutes, or B_test.
```

Claude Code:

```text
/devpilot-research-agent optimize this repo for <metric>. You may edit source through executor branches, run <eval command> on B_dev, and stop after 5 cycles or 4 hours. Ask before package installs, data downloads, GPU jobs longer than 30 minutes, or B_test.
```

Expected behavior:

- The wrapper inspects local context and git state.
- If target, metric, eval, permissions, or budget are ambiguous, it asks a
  compact clarification checkpoint.
- Once the contract is clear, it loads the orchestrator.
- The orchestrator initializes `.devpilot/sessions/<run_name>/`.
- The coordinator manages candidates through the Idea Tree.
- Executors implement and evaluate ideas within the allowed edit surface.
- Merge/eval protects B_test and trunk.
- The run ends with a `REPORT.md`.

### Smoke or forward test

Codex:

```text
$devpilot-research-agent try a one-cycle smoke run. Use cached metrics/defaults where safe, do not run training, do not edit source, do not create worktrees, and write an DevPilot-style report.
```

Claude Code:

```text
/devpilot-research-agent try a one-cycle smoke run. Use cached metrics/defaults where safe, do not run training, do not edit source, do not create worktrees, and write an DevPilot-style report.
```

Expected artifacts:

```text
.devpilot/sessions/<run_name>/.coordinator/idea_tree.json
.devpilot/sessions/<run_name>/.coordinator/idea_tree.md
.devpilot/sessions/<run_name>/experiments/<node_id>/executor_prompt.md
.devpilot/sessions/<run_name>/experiments/<node_id>/report.md
.devpilot/sessions/<run_name>/experiments/<node_id>/metrics.json
.devpilot/sessions/<run_name>/REPORT.md
```

### Ambiguous request

For a vague request such as:

```text
$devpilot-research-agent make this model better overnight
```

the wrapper should ask a compact checkpoint similar to:

```text
I can start, but I need these defaults confirmed:
- target: <cwd>
- objective/metric: <inferred or unknown>
- eval: <inferred command or unknown>
- run mode: smoke / real
- permissions: may edit code? may run training/GPU? may install packages?
- budget: <cycles/time>

Reply "yes" to accept, or edit any line.
```

This mirrors the native DevPilot intake and Research Contract experience.

## Runtime Guardrails

- Install all `devpilot-*` skill directories, not only `devpilot-research-agent`.
- Users should invoke only the public entrypoint. Internal phase skills are
  loaded by the wrapper/orchestrator.
- `try`, `test`, `demo`, and `smoke` requests default to smoke-only.
- Smoke mode does not run training, downloads, long GPU jobs, real worktrees,
  or real merges.
- Real training, package installation, data download, B_test use, and merge
  operations require explicit user permission.
- B_test must not be used for routine iteration.
- The coordinator should not directly edit project source. Source changes go
  through executor/worktree behavior.
- Do not inspect long logs with raw `cat`/`grep`. Prefer:

```bash
python skills/devpilot-agent-tools/scripts/devpilot_state.py parse-log --log <log> --metric <metric>
```

## Validation Commands

Run these from the DevPilot repository root.

Compile the deterministic helper:

```bash
python -m py_compile skills/devpilot-agent-tools/scripts/devpilot_state.py
```

Validate every skill frontmatter:

```bash
find skills -mindepth 1 -maxdepth 1 -type d | sort | while read -r d; do
  printf '%s: ' "$d"
  uv run --with pyyaml python <path-to-skill-creator>/scripts/quick_validate.py "$d"
done
```

Validate OpenAI metadata:

```bash
uv run --with pyyaml python - <<'PY'
from pathlib import Path
import yaml
for path in sorted(Path("skills").glob("*/agents/openai.yaml")):
    data = yaml.safe_load(path.read_text())
    assert isinstance(data, dict), path
    assert isinstance(data.get("interface"), dict), path
    for key in ("display_name", "short_description", "default_prompt"):
        assert data["interface"].get(key), (path, key)
print("openai.yaml valid:", len(list(Path("skills").glob("*/agents/openai.yaml"))))
PY
```

Validate a smoke session:

```bash
python skills/devpilot-agent-tools/scripts/devpilot_state.py check --cwd <target_repo> --run-name <run_name> \
  --require-report --require-experiment --require-executor-prompt
```

## Verified Behavior

The suite has been validated with both static checks and a dynamic Codex smoke
run in a disposable target repository outside the DevPilot checkout. A reproducible
validation should confirm:

- All 11 skills pass `quick_validate.py`.
- All 11 `agents/openai.yaml` files parse correctly.
- `devpilot_state.py` compiles.
- `devpilot_state.py check` returns `OK` with the expected artifact flags.
- A fresh Codex session starting only from `$devpilot-research-agent` performs
  intake, loads the orchestrator and phase skills, maintains an Idea Tree,
  dispatches through executor-style behavior, and writes DevPilot-style artifacts.
- Smoke runs do not execute package syncs, training scripts, GPU training,
  downloads, full evals, worktrees, merges, or source edits unless the user
  explicitly requested a real run.

## Troubleshooting

### Only one skill appears, or internal skills do not load

You probably copied only `devpilot-research-agent`. Copy every `devpilot-*` skill
directory and restart Codex or Claude Code.

### Claude Code does not trigger `/devpilot-research-agent`

Check the installation path:

- User-level: `~/.claude/skills/devpilot-research-agent/SKILL.md`
- Project-level: `<target_repo>/.claude/skills/devpilot-research-agent/SKILL.md`

You can also explicitly prompt:

```text
Read .claude/skills/devpilot-research-agent/SKILL.md and follow it as the public entrypoint.
```

### Codex does not trigger `$devpilot-research-agent`

Check that the skill exists at:

```text
${CODEX_HOME:-$HOME/.codex}/skills/devpilot-research-agent/SKILL.md
```

Restart Codex after installation. For a one-off test, use `--add-dir` and
explicitly tell the agent to start from `devpilot-research-agent`.

### When should I use native DevPilot instead?

Use the native `devpilot` CLI when you want a production DevPilot run and the native
runtime is installed. Use this skill suite when you want to:

- Reproduce DevPilot-style behavior in Codex or Claude Code.
- Work in an environment without native DevPilot tools.
- Run smoke or forward tests.
- Teach an agent to follow DevPilot's research discipline.
- Share a cross-platform `SKILL.md`-based workflow.
