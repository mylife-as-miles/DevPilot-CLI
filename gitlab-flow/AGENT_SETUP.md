# DevPilot on GitLab — use custom agents (recommended)

GitLab **custom flows cannot call AI Catalog agents** today (planned in [gitlab-org#21832](https://gitlab.com/groups/gitlab-org/-/work_items/21832)). Flow YAML is also capped at **64 KiB** per version — too small to embed full DevPilot prompts.

**Use four custom agents** instead. Each agent holds one mega-prompt; you orchestrate them in Duo Chat (or via work items).

## Prerequisites

1. Commit these files to `gitlab-ai-hackathon/transcend/35314637`:

   - `GITLAB_INTAKE_MEGA_PROMPT.txt`
   - `GITLAB_COORDINATOR_MEGA_PROMPT.txt`
   - `GITLAB_EXECUTOR_MEGA_PROMPT.txt`
   - `GITLAB_SEARCH_MEGA_PROMPT.txt`

2. Enable **Orbit** tools on the project.
3. Enable **custom agents** for the group (Settings → GitLab Duo).

## Create the four agents

For each agent: **AI → Agents → New agent** (or AI Catalog → New agent).

Paste the **entire** corresponding `GITLAB_*_MEGA_PROMPT.txt` into **System prompt** (from the `SECTION A` block through the end, or the whole file).

| Display name | System prompt file | Suggested tools |
|--------------|-------------------|-----------------|
| **DevPilot Intake** | `GITLAB_INTAKE_MEGA_PROMPT.txt` | List/get/create work items, create plan, blob search, Orbit (all 5) |
| **DevPilot Coordinator** | `GITLAB_COORDINATOR_MEGA_PROMPT.txt` | Above + get pipeline errors, job logs, CI linter, run tests, MR read/create |
| **DevPilot Executor** | `GITLAB_EXECUTOR_MEGA_PROMPT.txt` | Read repo, edit/create files, run command, run git, run tests, MR tools, Orbit |
| **DevPilot Search** | `GITLAB_SEARCH_MEGA_PROMPT.txt` | Blob search, grep, read file, doc/issue/MR search, Orbit |

Enable all four agents on the project after publishing.

## Run order (matches native DevPilot)

```text
You
 │
 ▼
DevPilot Intake          → research contract
 │
 ▼
DevPilot Coordinator     ◄──────────────────────────┐
 │   (INIT → OBSERVE → IDEATE → SELECT → DISPATCH)   │
 │                                                    │
 ├──► DevPilot Executor  (one experiment) ───────────┤
 │                                                    │
 ├──► DevPilot Search    (validated winners only) ───┤
 │                                                    │
 └──► REPORT.md / stop ─────────────────────────────┘
```

### Step 1 — Intake

Open **DevPilot Intake** in Duo Chat:

```text
Goal: <your research objective>
Project: gitlab-ai-hackathon/transcend/35314637
```

Save the **research contract** (work item note or copy the full reply).

### Step 2 — Coordinator

Open **DevPilot Coordinator**. Paste:

```text
Project: gitlab-ai-hackathon/transcend/35314637
Run name: <short-id e.g. auth-coverage-1>

Research contract:
<paste intake output>

Run INIT, then the DevPilot cycle. Persist the Idea Tree at
.devpilot/sessions/<run_name>/.coordinator/idea_tree.json
```

### Step 3 — Executor (when coordinator dispatches)

When the coordinator selects an experiment, open **DevPilot Executor**:

```text
Project: gitlab-ai-hackathon/transcend/35314637
Run name: <same run_name>

Coordinator dispatch:
<paste coordinator's dispatch package>

Implement one experiment. Evaluate on B_dev only. Return structured report.
```

Paste the executor report back into **DevPilot Coordinator** for DECIDE / next cycle.

### Step 4 — Search (validated winners only)

When a node is `done` or `merged` **and** beat trunk, open **DevPilot Search**:

```text
Project: gitlab-ai-hackathon/transcend/35314637

Validated hypothesis:
<paste from coordinator / idea tree node>

Experiment report:
<paste executor report>
```

Paste search output back to the **Coordinator** (updates `related_work` on the node).

### Repeat

Loop steps 2–4 until the coordinator writes `REPORT.md` or hits your cycle budget.

## Optional: slim flow + agents together

If you still want a **flow** entry in the catalog (under 64 KiB):

1. Use `devpilot-flow-config.yaml` (loads prompts from repo files at runtime).
2. **Or** skip the flow entirely — the four agents above are the real DevPilot stack.

Do **not** use `devpilot-flow-config-full.yaml` in the GitLab UI — it exceeds the size limit.

## Hackathon demo script (3 min)

1. Show Intake turning a vague goal into a contract.
2. Show Coordinator IDEATE + dispatch one experiment.
3. Show Executor branch + `run_tests` / score on B_dev.
4. Show Orbit `query_graph` on a hot path.
5. Show Search related-work on a winning node.

## Why not one big flow?

| Limitation | Agents | Flow (full embed) | Flow (slim) |
|------------|--------|-------------------|-------------|
| 64 KiB YAML cap | N/A | Fails | OK |
| Reference catalog agents | N/A | Not supported | Not supported |
| Full verbatim prompts | Yes | Yes (too big) | Via repo files |
| Multi-cycle coordinator | Manual loop | Hub only if it fit | Hub via repo load |
