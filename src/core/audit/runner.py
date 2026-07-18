"""Run iFixAi audits through DevPilot's safe local wrapper."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..._app import CONFIG_DIR_NAME
from .ifixai_bridge import IfixAiResult, find_project_root, redact_args, redact_text, run_ifixai


MOCK_API_KEY = "devpilot-mock-key"
DEFAULT_SUITE = "smoke"
DEFAULT_FORMAT = "both"
DEFAULT_TIMEOUT_SECONDS = 900
PROVIDER_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "azure": "AZURE_OPENAI_API_KEY",
    "bedrock": "AWS_ACCESS_KEY_ID",
    "huggingface": "HUGGINGFACE_API_KEY",
    "http": "IFIXAI_API_KEY",
    "langchain": "IFIXAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


@dataclass(frozen=True)
class AuditRunConfig:
    """Configuration for a single audit run."""

    provider: str = "mock"
    suite: str = DEFAULT_SUITE
    model: str | None = None
    endpoint: str | None = None
    eval_mode: str | None = None
    api_key_env: str | None = None
    output_dir: Path | None = None
    dry_run: bool = False
    timeout: int = DEFAULT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class AuditRunOutcome:
    """Audit run result plus local output metadata."""

    result: IfixAiResult
    output_dir: Path
    display_args: list[str]
    secrets_used: int


class AuditRunError(ValueError):
    """Raised when a run would violate DevPilot audit safety rules."""


def audit_output_dir(project_root: Path | str | None = None) -> Path:
    root = find_project_root(project_root)
    return root / CONFIG_DIR_NAME / "audit" / "ifixai-results"


def audit_reliability_dir(project_root: Path | str | None = None) -> Path:
    root = find_project_root(project_root)
    return root / CONFIG_DIR_NAME / "audit" / "ifixai-runs"


def is_external_provider(provider: str) -> bool:
    return provider.lower() != "mock"


def default_api_key_env(provider: str) -> str | None:
    return PROVIDER_KEY_ENV.get(provider.lower())


def build_run_args(config: AuditRunConfig, *, api_key: str | None = None) -> list[str]:
    """Build iFixAi ``run`` args. The returned list may contain a secret."""

    provider = (config.provider or "mock").lower()
    suite = config.suite or DEFAULT_SUITE
    output = config.output_dir or audit_output_dir()
    reliability_output = output.parent / "ifixai-runs"
    eval_mode = config.eval_mode or ("self" if provider == "mock" else "standard")

    args = [
        "run",
        "--provider",
        provider,
        "--suite",
        suite,
        "--output",
        str(output),
        "--format",
        DEFAULT_FORMAT,
        "--reliability-out",
        str(reliability_output),
        "--eval-mode",
        eval_mode,
        "--no-telemetry",
    ]
    if config.model:
        args.extend(["--model", config.model])
    if config.endpoint:
        args.extend(["--endpoint", config.endpoint])
    if api_key:
        args.extend(["--api-key", api_key])
    if config.dry_run:
        args.append("--dry-run")
    return args


def run_audit(config: AuditRunConfig, *, project_root: Path | str | None = None) -> AuditRunOutcome:
    """Run an iFixAi audit with local output and redacted reporting."""

    root = find_project_root(project_root)
    output = config.output_dir or audit_output_dir(root)
    output.mkdir(parents=True, exist_ok=True)
    provider = (config.provider or "mock").lower()

    secrets: list[str] = []
    api_key: str | None = None
    if provider == "mock":
        api_key = MOCK_API_KEY
        secrets.append(api_key)
    else:
        env_name = config.api_key_env or default_api_key_env(provider)
        if not env_name:
            raise AuditRunError(
                f"No default API key environment variable is known for provider '{provider}'. "
                "Pass --api-key-env NAME."
            )
        api_key = os.environ.get(env_name)
        if not api_key:
            raise AuditRunError(
                f"Provider '{provider}' requires an API key in environment variable {env_name}."
            )
        secrets.append(api_key)

    effective = AuditRunConfig(
        provider=provider,
        suite=config.suite or DEFAULT_SUITE,
        model=config.model,
        endpoint=config.endpoint,
        eval_mode=config.eval_mode,
        api_key_env=config.api_key_env,
        output_dir=output,
        dry_run=config.dry_run,
        timeout=config.timeout,
    )
    args = build_run_args(effective, api_key=api_key)
    result = run_ifixai(args, cwd=root, timeout=effective.timeout)
    result = IfixAiResult(
        argv=redact_args(result.argv),
        returncode=result.returncode,
        stdout=redact_text(result.stdout, secrets),
        stderr=redact_text(result.stderr, secrets),
        cwd=result.cwd,
        source=result.source,
        error=result.error,
        timed_out=result.timed_out,
    )
    return AuditRunOutcome(
        result=result,
        output_dir=output,
        display_args=redact_args(args),
        secrets_used=len([secret for secret in secrets if secret]),
    )


def format_display_command(args: Sequence[str]) -> str:
    """Render args for humans with shell-safe quoting kept simple."""

    return " ".join(_quote(part) for part in args)


def _quote(value: str) -> str:
    if not value:
        return "''"
    if any(ch.isspace() for ch in value):
        return '"' + value.replace('"', '\\"') + '"'
    return value
