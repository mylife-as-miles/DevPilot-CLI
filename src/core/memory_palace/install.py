"""Safe installation guidance for the optional MemPalace runtime."""

from __future__ import annotations


def install_guidance() -> str:
    """Return manual setup guidance without mutating the environment."""

    return """\
MemPalace is vendored under vendor/mempalace and kept as upstream MIT source.
DevPilot does not install MemPalace dependencies into its core environment.

Safe isolated setup options:
  uv tool install mempalace
  pipx install mempalace

Project-local editable setup:
  python -m venv .venv-mempalace
  .venv-mempalace\\Scripts\\Activate.ps1
  python -m pip install -e vendor/mempalace

POSIX shell equivalent:
  python -m venv .venv-mempalace
  . .venv-mempalace/bin/activate
  python -m pip install -e vendor/mempalace

Zero-install fallback if uvx is available:
  uvx mempalace --help

Do not install ChromaDB into DevPilot's normal environment unless you
intentionally choose that path.
"""
