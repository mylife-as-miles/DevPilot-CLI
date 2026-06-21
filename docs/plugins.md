# Plugins

A plugin retargets DevPilot to a **domain** without changing any code. It is a single YAML
file that declares how to evaluate work, what must stay protected, what outputs are
required, a compute budget, and some domain guidance for the agents.

!!! abstract "Plugin vs. Skill in one line"
    A **plugin** describes *what to optimize* — the eval rules, protected files, and budget
    for a whole domain. A [Skill](skills.md) sharpens *how the agent reasons* at one step.
    You can use either alone, or both together.

!!! question "Do I even need a plugin?"
    **No, not to start.** For a one-off task, just prepare a repo and launch `devpilot` (see
    [Preparing a Benchmark](preparing-a-benchmark.md)). Reach for a plugin only when you run
    the **same kind of benchmark repeatedly** and want every run to use identical eval
    rules, guardrails, and budget.

## Activating a plugin

Put one line in your project's config (`research_config.yaml`, `devpilot.yaml`, or
`autoresearch.yaml`), then launch the interactive CLI from the project directory:

```yaml title="research_config.yaml"
plugin: mle_kaggle        # the only line that switches domains
```

```bash
cd my_competition
devpilot
```

DevPilot auto-discovers the config in the project directory; the intake chat then runs with
the plugin's contract and guidance already applied.

!!! tip "Try a plugin without editing files"
    You can also pick a plugin from inside the intake chat — type `/` to use a slash
    command:

    ```text
    /plugin load mle_kaggle mle_bench_lite   # load a plugin (and an optional profile)
    /plugin unload                           # ignore the configured plugin this run
    /plugin reset                            # go back to whatever your config specifies
    ```

    These choices apply to the single run you're about to launch and don't change your
    config.

## The plugin format

Every plugin follows the **same standard shape**. A minimal one needs only a name and an
eval contract:

```yaml title="minimal_plugin.yaml"
name: my_domain
description: "One line on what this plugin optimizes"
schema_version: 1

eval_contract:
  metric_direction: maximize          # or: minimize
  eval_cmd: "bash {cwd}/eval.sh"      # {cwd} -> project directory
```

Everything else is optional and layered on top. The full set of fields:

| Field | Required | Purpose |
| --- | --- | --- |
| `name` | ✓ | Plugin identifier, referenced by `plugin:` in config. |
| `description` | ✓ | One-line summary shown in `devpilot` plugin listings. |
| `schema_version` |  | Format version (currently `1`). |
| `eval_contract` | ✓ | How to score: `metric_direction`, `eval_cmd` (with `{cwd}` substitution), and optional `submission_path` / `sample_submission_path`. |
| `protected_paths` |  | Glob patterns that are read-only to executors — your data and harness. |
| `required_outputs` |  | Artifacts that must exist for a run to count as valid. |
| `profiles` |  | Named budget bundles (`max_cycles`, `max_tree_depth`, `executor_timeout`, `time_budget`), selected with `plugin_profile`. |
| `config_overrides` |  | Default config values the plugin sets for every run. |
| Prompt injections |  | Domain guidance merged into the agents' system prompts (see below). |

### Prompt injection points

Domain guidance is added at six well-defined points — four for the **coordinator** (the
research director) and two for the **executor** (the engineer that runs one experiment):

| Key | Injected into |
| --- | --- |
| `meta_preamble_inject` | Top of the coordinator prompt — overall objective and strategy. |
| `meta_init_inject` | Coordinator's discovery/setup phase. |
| `meta_ideate_inject` | Coordinator's idea-generation phase. |
| `meta_decide_inject` | Coordinator's merge/keep-or-prune decisions. |
| `sub_preamble_inject` | Top of the executor prompt. |
| `sub_workflow_inject` | Executor's workflow rules and guardrails. |

Each is plain markdown text. Use them to encode domain habits ("always produce a valid
baseline first", "never write to `data/`"), not to script a specific solution.

### Where each setting wins

Settings combine in a fixed priority order, lowest to highest:

```text
built-in defaults  <  plugin.config_overrides  <  profiles[active]  <  your YAML config  <  CLI flags
```

So a value you set in your own config always beats the plugin, and a CLI flag beats
everything.

## The bundled example: `mle_kaggle`

DevPilot ships one plugin, `mle_kaggle`, as a complete worked example for Kaggle / MLE-bench
competitions. It declares the eval contract, protects the data and harness, requires a
`submission.csv`, and bundles a benchmark budget profile:

```yaml title="src/plugins/mle_kaggle.yaml (excerpt)"
name: mle_kaggle
description: "Engineering optimization for Kaggle/MLE-bench competitions"
schema_version: 1

eval_contract:
  metric_direction: maximize
  eval_cmd: "bash {cwd}/eval.sh"
  submission_path: "submission.csv"
  sample_submission_path: "data/sample_submission.csv"

protected_paths:
  - "data/**"
  - "private/**"
  - "evaluation/**"

required_outputs:
  - "submission.csv"

profiles:
  mle_bench_lite:                 # 24 h MLE-Bench-Lite budget
    max_cycles: 20
    max_tree_depth: 4
    executor_timeout: 14400       # 4 h per executor
    time_budget: 86400            # 24 h total
```

Select the profile alongside the plugin:

```yaml title="research_config.yaml"
plugin: mle_kaggle
plugin_profile: mle_bench_lite
```

A ready-to-edit config lives at `examples/kaggle_config.example.yaml` in the repository.

## Writing your own plugin

1. Create a `plugins/` folder inside your project and add `my_domain.yaml` there:
   `<project>/plugins/my_domain.yaml`. DevPilot discovers project plugins from this folder
   (built-in plugins live alongside DevPilot and are always available too). Start from the
   minimal template above, or copy the bundled `mle_kaggle` plugin as a worked example.
2. Set `name`, `description`, and the `eval_contract` for your domain.
3. Add `protected_paths` / `required_outputs` if your task has data to guard or artifacts
   to produce.
4. Add a `profiles` entry with your compute budget.
5. Tune the agents with the injection points only if you need domain-specific behaviour.

Then activate it by name — either `plugin: my_domain` in your config, or `/plugin load
my_domain` in the chat — and launch `devpilot`. Pair it with a [Skill](skills.md) when you want
to shape *how* the agent reasons, not just what it optimizes.
