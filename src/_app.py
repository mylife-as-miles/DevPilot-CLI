"""Single-source-of-truth for the application's brand name.

Future renames only need to change APP_NAME below; all derived strings
(CLI command, config dir, config file) update automatically. Do not write
the literal string "devpilot" anywhere else in the codebase.
"""

from pathlib import Path

APP_NAME = "devpilot"

CLI_COMMAND = APP_NAME

# Product taglines, shown on the splash banner and in `--help`. Kept here as a
# single source of truth so the two surfaces never drift. TAGLINE is the punchy
# hero line; TAGLINE_SUB explains what DevPilot does in plain language.
TAGLINE = "Autonomous research for your codebase."
TAGLINE_SUB = "Describe a goal — DevPilot proposes ideas, runs experiments, and keeps what improves your metric."

CONFIG_DIR_NAME = f".{APP_NAME}"
CONFIG_FILE_NAME = f"{APP_NAME}.yaml"

GLOBAL_CONFIG_DIR = Path.home() / f".{APP_NAME}"
GLOBAL_CONFIG_FILE = GLOBAL_CONFIG_DIR / "config.yaml"

# Legacy paths kept for one release so users with a pre-rename config
# don't lose their settings. The user_config loader falls back to these.
LEGACY_GLOBAL_CONFIG_DIR = Path.home() / ".autoresearch"
LEGACY_GLOBAL_CONFIG_FILE = LEGACY_GLOBAL_CONFIG_DIR / "config.yaml"
