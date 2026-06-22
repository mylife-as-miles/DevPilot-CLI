# DevPilot — GitLab Duo setup

Project: `gitlab-ai-hackathon/transcend/35314637`

## Recommended: custom agents, not a big flow

GitLab flows **cannot invoke your AI Catalog agents** yet, and embedded flow YAML is limited to **64 KiB** (you hit: *"Latest version definition is too large"*).

**→ Follow [AGENT_SETUP.md](AGENT_SETUP.md)** to create four catalog agents from the `GITLAB_*_MEGA_PROMPT.txt` files.

## Optional: slim flow (under 64 KiB)

Use this only if you want a single **DevPilot** flow in the catalog. It does **not** call your agents — it loads the same mega-prompt **files from the repo** at runtime.

**Display name:** `DevPilot`

**Config file:** `devpilot-flow-config.yaml` (~7 KB)

1. Commit all four `GITLAB_*_MEGA_PROMPT.txt` files to the GitLab project.
2. **AI → Flows → New flow** → paste `devpilot-flow-config.yaml`.
3. Trigger with `goal`, `project_id`, optional `run_name`, `max_cycles`.

```bash
python _gen_gitlab_flow.py
```

## Do not paste these in the GitLab UI

| File | Size | Reason |
|------|------|--------|
| `devpilot-flow-config-full.yaml` | ~99 KiB | Exceeds 64 KiB limit |
| `devpilot-loop-flow-config.yaml` | ~148 KiB | Exceeds limit |
| `devpilot-demo-linear-flow-config.yaml` | ~143 KiB | Exceeds limit |

Local / GDK only.

## Agents vs slim flow

| | Four catalog agents | Slim flow |
|---|---------------------|-----------|
| Full prompts | In agent system prompt | Loaded from repo files |
| Orchestration | You chain in Duo Chat | Automatic intake → coordinator |
| Executor / Search | Separate agents | Coordinator does both via tools |
| Best for | Hackathon demo + fidelity | One-click trigger |

## Trigger inputs (slim flow)

| Input | Required |
|-------|----------|
| `goal` | yes |
| `project_id` | yes |
| `run_name` | optional |
| `max_cycles` | optional (default 3) |

## Before running

1. Enable **Orbit** tools.
2. Match `toolset` slugs to your GitLab tool picker.
3. Commit mega-prompt files to the repo (slim flow) **or** paste into agents ([AGENT_SETUP.md](AGENT_SETUP.md)).
