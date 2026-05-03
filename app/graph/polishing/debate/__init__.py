"""Debate Subgraph 模块 - Author-Editor 对抗循环"""

from app.graph.polishing.debate.state import DebateState
from app.graph.polishing.debate.nodes import (
    author_node,
    editor_node,
    increment_iteration_node,
    finalize_debate_node,
    should_continue_debate,
)
from app.graph.polishing.debate.builder import get_debate_graph

__all__ = [
    # State
    "DebateState",
    # Nodes
    "author_node",
    "editor_node",
    "increment_iteration_node",
    "finalize_debate_node",
    # Conditional Edges
    "should_continue_debate",
    # Builder
    "get_debate_graph",
]
