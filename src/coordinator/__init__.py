"""Coordinator — devpilot-guided research orchestrator with Idea Tree.

The coordinator orchestrates automated research through an Idea Tree.
It dispatches executors (Research Agents) to implement and test ideas,
learns from results, and systematically explores promising directions.
"""

from .config import CoordinatorConfig
from .idea_tree import IdeaTree, Node
from .orchestrator import CoordinatorOrchestrator

__all__ = [
    "CoordinatorConfig",
    "IdeaTree",
    "Node",
    "CoordinatorOrchestrator",
]
