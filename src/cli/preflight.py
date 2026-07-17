"""Preflight environment checks.

Runs before the user spends any LLM tokens on a research session.
This iteration is check-only: surfaces problems with clear messages but
does not auto-fix. Auto-fix flows (interactive git init, eval scaffolding,
API key prompt) are a follow-up.

Each check returns a CheckResult; PreflightChecker.run_all() returns
True iff all checks passed (status == "pass").
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import typer


@dataclass
class CheckResult:
    name: str
    status: str  # "pass" | "warn" | "fail"
    message: str
    hint: str | None = None  # actionable next step shown when not pass


class PreflightChecker:
    """Run a fixed list of checks and report status.

    Checks:
      1. LLM credentials available (env var or explicit)
      2. cwd exists and contains files
      3. git installed and repo not dirty (warn if no repo at all)
      4. an eval entry point exists (eval.sh / evaluate.py / similar)
    """

    EVAL_CANDIDATES = ("eval.sh", "evaluate.sh", "run_eval.sh",
                       "evaluate.py", "eval.py")

    def __init__(self, cwd: Path, provider: str | None,
                 explicit_api_key: str | None = None,
                 *, verbose: bool = False,
                 orbit: Any | None = None) -> None:
        self.cwd = cwd.resolve()
        self.provider = (provider or "anthropic").lower()
        self.explicit_api_key = explicit_api_key
        self.verbose = verbose
        self.orbit = orbit

    def run_all(self) -> bool:
        """Print results and return True iff none failed (legacy)."""
        results = self.run_all_collect()
        return all(r.status != "fail" for r in results)

    def check_llm_credentials(self, *, render: bool = True) -> CheckResult:
        """Run just the LLM credential check.

        The intake chat itself needs an LLM call, so the CLI uses this as a
        zero-token gate before constructing the planning agent. Full project
        preflight still runs later against the final target directory.
        """
        result = self._check_llm()
        if render and (self.verbose or result.status == "fail"):
            self._render(result)
        return result

    def run_all_collect(self, *, render: bool = True) -> list[CheckResult]:
        """Run every check, render to stdout, return all results.

        Non-blocking — even fails are returned, not raised. Caller decides
        what to do (the intake agent uses these as initial context to
        discuss with the user).

        By default only ``fail`` results are rendered to keep the launch
        flow quiet — pass/warn pile up as visual noise on repeated runs.
        Set ``verbose=True`` to print every check.
        """
        checks: list[Callable[[], CheckResult]] = [
            self._check_llm,
            self._check_cwd,
            self._check_git,
            self._check_eval,
        ]
        if self._orbit_enabled():
            checks.append(self._check_orbit)
        results: list[CheckResult] = []
        for check in checks:
            result = check()
            if render and (self.verbose or result.status == "fail"):
                self._render(result)
            results.append(result)
        return results

    @staticmethod
    def _render(r: CheckResult) -> None:
        if r.status == "pass":
            typer.secho(f"  [ok]   {r.name}: {r.message}", fg=typer.colors.GREEN)
        elif r.status == "warn":
            typer.secho(f"  [warn] {r.name}: {r.message}", fg=typer.colors.YELLOW)
            if r.hint:
                typer.echo(f"         hint: {r.hint}")
        else:
            typer.secho(f"  [fail] {r.name}: {r.message}", fg=typer.colors.RED, err=True)
            if r.hint:
                typer.secho(f"         hint: {r.hint}", fg=typer.colors.RED, err=True)

    # ── Check 1: LLM credentials ───────────────────────────────────

    _PROVIDER_ENV = {
        "auto": None,      # backend chosen from the model name; either key works
        "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "openai": ("OPENAI_API_KEY",),
        "openai-responses": ("OPENAI_API_KEY",),
        "openai-chat": ("OPENAI_API_KEY",),
        "litellm": None,  # depends on chosen model
    }

    def _check_llm(self) -> CheckResult:
        if self.provider == "openai-oauth":
            return self._check_openai_oauth()

        if self.provider not in self._PROVIDER_ENV:
            return CheckResult(
                "llm", "fail",
                f"unknown provider={self.provider}",
                hint="run `devpilot setup` and choose anthropic, openai, or litellm",
            )

        if self.explicit_api_key:
            return CheckResult("llm", "pass",
                               f"api key supplied for provider={self.provider}")

        env_vars = self._PROVIDER_ENV.get(self.provider)
        if env_vars is None:
            # litellm or unknown provider — best-effort guess
            for v in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
                if os.environ.get(v):
                    return CheckResult("llm", "pass",
                                       f"found ${v} (provider={self.provider})")
            return CheckResult(
                "llm", "warn",
                f"no obvious api key in environment for provider={self.provider}",
                hint="set ANTHROPIC_API_KEY / OPENAI_API_KEY, or run `devpilot setup`",
            )

        for env_var in env_vars:
            if os.environ.get(env_var):
                return CheckResult("llm", "pass",
                                   f"found ${env_var} (provider={self.provider})")
        expected = " or ".join(f"${v}" for v in env_vars)
        primary = env_vars[0]
        if len(env_vars) == 1:
            expected = f"${primary}"
        return CheckResult(
            "llm", "fail",
            f"missing {expected} for provider={self.provider}",
            hint=f"export {primary}=... or run `devpilot setup`",
        )

    @staticmethod
    def _check_openai_oauth() -> CheckResult:
        """ChatGPT subscription auth lives in a token file, not an env var."""
        try:
            from ..core.oauth import openai as oauth
        except ImportError:
            return CheckResult(
                "llm", "fail", "openai oauth support unavailable",
                hint="reinstall devpilot",
            )
        tokens = oauth.load_tokens()
        if tokens is None:
            return CheckResult(
                "llm", "fail",
                "not logged in to ChatGPT (provider=openai-oauth)",
                hint="run `devpilot login openai`",
            )
        plan = tokens.plan_type or "unknown"
        return CheckResult("llm", "pass",
                           f"ChatGPT subscription token found (plan={plan})")

    # ── Check 2: codebase ──────────────────────────────────────────

    def _check_cwd(self) -> CheckResult:
        if not self.cwd.exists():
            return CheckResult("cwd", "fail",
                               f"directory does not exist: {self.cwd}",
                               hint="pass --cwd <existing-dir>")
        visible = [p for p in self.cwd.iterdir() if not p.name.startswith(".")]
        if not visible:
            return CheckResult("cwd", "warn",
                               f"directory is empty: {self.cwd}",
                               hint="add code before starting a research run")
        return CheckResult("cwd", "pass",
                           f"{self.cwd} ({len(visible)} top-level entries)")

    # ── Check 3: git ───────────────────────────────────────────────

    def _check_git(self) -> CheckResult:
        if shutil.which("git") is None:
            return CheckResult("git", "fail", "git is not installed",
                               hint="install git before starting a research run")
        try:
            inside = subprocess.check_output(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.cwd, stderr=subprocess.DEVNULL, text=True,
            ).strip()
        except (subprocess.CalledProcessError, OSError):
            inside = "false"
        if inside != "true":
            return CheckResult(
                "git", "warn",
                "not a git repository (the agent uses branches to isolate experiments)",
                hint=f"cd {self.cwd} && git init && git add . && git commit -m init",
            )
        try:
            dirty = subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=self.cwd, stderr=subprocess.DEVNULL, text=True,
            ).strip()
        except subprocess.CalledProcessError:
            return CheckResult("git", "warn", "git status failed (corrupt repo?)")
        if dirty:
            n = len(dirty.splitlines())
            return CheckResult(
                "git", "fail",
                f"{n} uncommitted change(s) — repo must be clean before running",
                hint="git add -A && git commit, or git stash",
            )
        return CheckResult("git", "pass", "clean repository")

    # ── Check 4: eval script ───────────────────────────────────────

    def _check_eval(self) -> CheckResult:
        for name in self.EVAL_CANDIDATES:
            if (self.cwd / name).exists():
                return CheckResult("eval", "pass", f"found {name}")
        return CheckResult(
            "eval", "warn",
            f"no eval script found ({', '.join(self.EVAL_CANDIDATES)})",
            hint="create one (a command that prints a numeric score), or rely on the agent to find one",
        )

    # â”€â”€ Check 5: GitLab Orbit knowledge graph â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _orbit_value(self, key: str, default: Any = None) -> Any:
        if self.orbit is None:
            return default
        if isinstance(self.orbit, dict):
            return self.orbit.get(key, default)
        return getattr(self.orbit, key, default)

    def _orbit_enabled(self) -> bool:
        return bool(self._orbit_value("enabled", False))

    def _orbit_required(self) -> bool:
        return bool(self._orbit_value("required", False))

    def _orbit_status(self, status: str, message: str, hint: str | None = None) -> CheckResult:
        if status == "warn" and self._orbit_required():
            status = "fail"
        return CheckResult("orbit", status, message, hint=hint)

    def _check_orbit(self) -> CheckResult:
        mode = str(self._orbit_value("mode", "local") or "local").lower()
        command = str(self._orbit_value("command", "orbit") or "orbit").strip()
        executable = command.split()[0] if command else "orbit"
        if shutil.which(executable) is None:
            return self._orbit_status(
                "warn",
                f"enabled but `{executable}` is not installed",
                hint=(
                    "install Orbit Local: "
                    "irm https://gitlab.com/gitlab-org/orbit/knowledge-graph/-/raw/main/install.ps1 | iex"
                ),
            )

        if mode == "remote":
            group = self._orbit_value("remote_group")
            suffix = f" for group {group}" if group else ""
            return CheckResult("orbit", "pass", f"remote mode configured{suffix}")

        db_path = self._orbit_value("database_path")
        graph = Path(os.path.expanduser(str(db_path or "~/.orbit/graph.duckdb")))
        if not graph.exists():
            return self._orbit_status(
                "warn",
                f"local graph not found at {graph}",
                hint=f"run `{command} index {self.cwd}` before starting DevPilot",
            )
        return CheckResult("orbit", "pass", f"local graph found at {graph}")
