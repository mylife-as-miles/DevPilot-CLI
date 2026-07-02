"""YouTube channel — fetch video metadata and subtitles via ``yt-dlp``.

**Phase 1 rule**: never download video or audio.  We always pass
``--skip-download`` and only request subtitle/metadata files.
"""

from __future__ import annotations

import json
import os
import re
import tempfile

from ..subprocess_utils import is_available, run_safe


_YTDLP_BIN = "yt-dlp"


def is_ytdlp_available() -> bool:
    """Return True if ``yt-dlp`` is on PATH."""
    return is_available(_YTDLP_BIN)


def fetch(url: str, *, timeout: int = 30) -> str:
    """Fetch video metadata + subtitles for *url* without downloading media.

    Returns a human-readable summary.
    """
    if not is_ytdlp_available():
        return (
            "[youtube] `yt-dlp` is not installed.\n"
            "Install it: pip install yt-dlp   or   brew install yt-dlp"
        )

    url = url.strip()
    if not url:
        return "[youtube] URL must not be empty."

    with tempfile.TemporaryDirectory(prefix="devpilot_yt_") as tmpdir:
        # Step 1: dump JSON metadata (no media download)
        meta_cmd = [
            _YTDLP_BIN,
            "--skip-download",
            "--dump-json",
            "--no-warnings",
            url,
        ]
        try:
            meta_result = run_safe(meta_cmd, timeout=timeout)
        except FileNotFoundError:
            return "[youtube] yt-dlp binary not found despite being on PATH."
        except Exception as exc:
            return f"[youtube] yt-dlp metadata failed: {type(exc).__name__}: {exc}"

        if meta_result.returncode != 0:
            err = (meta_result.stderr or "").strip()
            return f"[youtube] yt-dlp error (exit {meta_result.returncode}): {err}"

        try:
            meta = json.loads(meta_result.stdout)
        except (json.JSONDecodeError, TypeError):
            return "[youtube] Could not parse yt-dlp JSON output."

        summary = _format_metadata(meta)

        # Step 2: try to get subtitles
        sub_cmd = [
            _YTDLP_BIN,
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", "en.*,zh.*,en,zh",
            "--sub-format", "vtt",
            "--no-warnings",
            "-o", os.path.join(tmpdir, "%(id)s.%(ext)s"),
            url,
        ]
        try:
            run_safe(sub_cmd, timeout=timeout)
        except Exception:
            pass  # subtitles are best-effort

        transcript = _read_subtitles(tmpdir)
        if transcript:
            summary += "\n\n── Transcript (auto) ──\n" + transcript

    return summary


def _format_metadata(meta: dict) -> str:
    """Render yt-dlp JSON metadata into compact readable text."""
    title = meta.get("title", "?")
    channel = meta.get("channel") or meta.get("uploader") or "?"
    duration = meta.get("duration")
    views = meta.get("view_count")
    upload = meta.get("upload_date", "")
    desc = meta.get("description", "")

    dur_str = _format_duration(duration) if duration else "?"
    if upload and len(upload) == 8:
        upload = f"{upload[:4]}-{upload[4:6]}-{upload[6:]}"

    lines = [
        f"Title:    {title}",
        f"Channel:  {channel}",
        f"Duration: {dur_str}",
        f"Views:    {views:,}" if isinstance(views, int) else f"Views:    {views or '?'}",
        f"Uploaded: {upload or '?'}",
    ]
    if desc:
        short_desc = desc[:500]
        if len(desc) > 500:
            short_desc += "..."
        lines.append(f"Description: {short_desc}")
    return "\n".join(lines)


def _format_duration(seconds: int | float) -> str:
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


def _read_subtitles(directory: str, max_chars: int = 4000) -> str:
    """Read the first VTT/SRT file found in *directory* and extract text lines."""
    for fname in sorted(os.listdir(directory)):
        if fname.endswith((".vtt", ".srt")):
            path = os.path.join(directory, fname)
            try:
                raw = open(path, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            text = _parse_subtitle_text(raw)
            if text:
                if len(text) > max_chars:
                    text = text[:max_chars] + "\n... [truncated]"
                return text
    return ""


def _parse_subtitle_text(raw: str) -> str:
    """Strip VTT/SRT timing cues and return plain text."""
    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        # skip WEBVTT header, NOTE lines, blank lines
        if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        # skip timing lines  00:00:01.000 --> 00:00:03.000
        if re.match(r"^\d{2}:\d{2}:\d{2}", line):
            continue
        # skip SRT sequence numbers
        if re.match(r"^\d+$", line):
            continue
        # strip inline tags like <c> </c>
        cleaned = re.sub(r"<[^>]+>", "", line).strip()
        if cleaned and (not lines or lines[-1] != cleaned):
            lines.append(cleaned)
    return "\n".join(lines)
