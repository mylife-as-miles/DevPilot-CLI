"""Evidence store for DevPilot Reach outputs.

Persists outputs from Reach tools as structured, append-only JSONL evidence
records under the active run/session directory.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any


def save_reach_evidence(
    workspace_dir: str | None,
    *,
    tool_name: str,
    source: str,
    query: str,
    content: str,
    title: str | None = None,
    summary: str | None = None,
    cycle_id: str | None = None,
    hypothesis_id: str | None = None,
) -> str | None:
    """Save a single evidence record to <workspace_dir>/reach_evidence.jsonl.

    If workspace_dir is None, does nothing.
    Returns the path to the evidence file if saved, else None.
    """
    if not workspace_dir:
        return None

    os.makedirs(workspace_dir, exist_ok=True)
    evidence_path = os.path.join(workspace_dir, "reach_evidence.jsonl")

    # Get ISO format timestamp in UTC
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    record = {
        "tool": tool_name,
        "source": source,
        "query": query,
        "title": title,
        "timestamp": timestamp,
        "content": content,
        "summary": summary,
        "cycle_id": cycle_id,
        "hypothesis_id": hypothesis_id,
    }

    with open(evidence_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return evidence_path


def list_reach_evidence(workspace_dir: str | None) -> list[dict[str, Any]]:
    """Return all evidence records stored in <workspace_dir>/reach_evidence.jsonl.

    If workspace_dir is None or the file does not exist, returns an empty list.
    """
    if not workspace_dir:
        return []

    evidence_path = os.path.join(workspace_dir, "reach_evidence.jsonl")
    if not os.path.exists(evidence_path):
        return []

    records = []
    with open(evidence_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                pass  # Skip corrupted lines

    return records


def search_reach_evidence(workspace_dir: str | None, query: str) -> list[dict[str, Any]]:
    """Search evidence records in <workspace_dir>/reach_evidence.jsonl.

    Matches query (case-insensitive substring) against:
      - tool name
      - source
      - query/input
      - title
      - content
      - summary
      - cycle_id
      - hypothesis_id
    """
    if not workspace_dir or not query:
        return []

    query_lower = query.lower()
    records = list_reach_evidence(workspace_dir)
    results = []

    for r in records:
        # Check all string fields
        match = False
        for field in ("tool", "source", "query", "title", "content", "summary", "cycle_id", "hypothesis_id"):
            val = r.get(field)
            if val and query_lower in str(val).lower():
                match = True
                break
        if match:
            results.append(r)

    return results
