# Tool Mapping

Use this reference when native DevPilot tools are unavailable.

| Native DevPilot behavior | Helper command |
|---|---|
| Create session and root tree | `devpilot_state.py init` |
| `TreeView(format="compact")` | `devpilot_state.py view --format compact` |
| `TreeView(format="full")` | `devpilot_state.py view --format full` |
| `TreeView(format="node", node_id=...)` | `devpilot_state.py view --format node --node-id ...` |
| `TreeView(format="pending")` | `devpilot_state.py view --format pending` |
| `TreeView(format="constraints")` | `devpilot_state.py view --format constraints` |
| `TreeAddNode` | `devpilot_state.py add --parent-id ... --hypothesis ...` |
| `TreeUpdateNode` | `devpilot_state.py update --node-id ...` |
| `TreeSetMeta` | `devpilot_state.py meta --set key=value` |
| `TreePrune` | `devpilot_state.py prune --node-id ... --reason ...` |
| `TreePropagate` | `devpilot_state.py propagate --node-id ...` |
| B_dev/B_test eval capture | `devpilot_state.py eval --split dev/test --cmd ...` |
| Cached metric extraction from logs | `devpilot_state.py parse-log --log ... --metric ...` |
| Build executor prompt | `devpilot_state.py prompt-executor --node-id ...` |
| Build smoke-only executor prompt | `devpilot_state.py prompt-executor --node-id ... --smoke` |
| Record executor result | `devpilot_state.py record --node-id ...` |
| Create a worktree | `devpilot_state.py worktree --node-id ...` |
| Merge with B_test guard | `devpilot_state.py merge --source-branch ... --node-id ...` |
| Validate tree file | `devpilot_state.py check` |
| Generate `REPORT.md` | `devpilot_state.py report` |

The helper intentionally does not replace the real multi-agent runtime. It
provides durable state and deterministic guardrails so a host agent can emulate
the open-source behavior during smoke tests and skill-driven runs.
