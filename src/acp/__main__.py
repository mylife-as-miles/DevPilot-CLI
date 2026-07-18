from __future__ import annotations

import asyncio

from .agent import run_stdio_agent


if __name__ == "__main__":
    asyncio.run(run_stdio_agent())
