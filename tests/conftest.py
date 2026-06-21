"""Pytest bootstrap.

DevPilot's code lives under ``src/`` but is imported as the ``devpilot`` package.
This conftest maps the package onto ``src/`` once, before collection, so test
modules can simply ``import devpilot...`` with no per-file boilerplate and no
install step. (The older standalone tests bootstrap themselves too; both paths
are idempotent via the ``"devpilot" not in sys.modules`` guard.)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

if "devpilot" not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        "devpilot",
        _ROOT / "src" / "__init__.py",
        submodule_search_locations=[str(_ROOT / "src")],
    )
    assert _spec and _spec.loader
    _devpilot = importlib.util.module_from_spec(_spec)
    sys.modules["devpilot"] = _devpilot
    _spec.loader.exec_module(_devpilot)
