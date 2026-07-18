"""Optional Headroom-backed compression helpers."""

from .bridge import build_headroom_command, find_vendored_headroom, is_headroom_available, run_headroom
from .runner import compress_text_file, conservative_compress_text
from .types import RunResult

__all__ = [
    "RunResult",
    "build_headroom_command",
    "compress_text_file",
    "conservative_compress_text",
    "find_vendored_headroom",
    "is_headroom_available",
    "run_headroom",
]
