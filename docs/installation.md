# Installation

## Requirements

- **Python ≥ 3.10**
- **Git** (DevPilot runs each experiment in an isolated git worktree)
- An API key for at least one LLM provider (Anthropic, OpenAI, or any
  OpenAI-compatible endpoint via LiteLLM)

## Install

```bash
pip install devpilot-agent          # or: uv pip install devpilot-agent
```

That single command installs DevPilot and the `devpilot` command into your current Python
environment. We recommend a virtual environment so it stays isolated:

=== "venv + pip"

    ```bash
    python -m venv .venv
    source .venv/bin/activate        # Windows: .venv\Scripts\activate
    pip install devpilot-agent
    ```

=== "uv"

    ```bash
    uv venv
    source .venv/bin/activate
    uv pip install devpilot-agent
    ```

!!! tip "Upgrading"
    Pull the latest release with `pip install -U devpilot-agent`.

## Install from source (development)

To hack on DevPilot itself, install it editable from a clone:

```bash
git clone https://github.com/RUC-NLPIR/DevPilot.git
cd DevPilot
pip install -e .          # or: uv pip install -e .
```

!!! info "Why editable (`-e`)?"
    An editable install lets you pull updates with `git pull` without reinstalling —
    ideal when you're modifying DevPilot's own source.

## Verify

```bash
devpilot version
devpilot doctor      # checks PATH, venv leakage, git, and API keys
```

`devpilot doctor` is the fastest way to catch a broken setup — it reports which `devpilot` your
shell resolves, which Python it runs on, whether `git` is available, and whether your
user config exists.

## Optional: a global `devpilot` command with pipx

If you'd rather have `devpilot` available in **every** directory without activating a venv,
install it with [pipx](https://pipx.pypa.io) — it manages the isolated environment for
you:

```bash
pipx install devpilot-agent          # install globally
pipx upgrade devpilot-agent          # upgrade later
```

## Troubleshooting

!!! failure "`devpilot: command not found`"
    The package was installed into an environment that isn't active or on your `PATH`.
    Activate the right virtual environment, or use the pipx install above. Run
    `devpilot doctor` for a diagnosis.

## Next steps

- [Quickstart](quickstart.md) — configure a provider and start your first run.
- [Configuration](configuration.md) — every option, with examples.
