"""Debate Subgraph 状态定义

本模块定义 Author-Editor 对抗循环子图的状态结构。
"""

import operator
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import BaseMessage

from app.graph.polishing.state import DebateRound


class DebateState(TypedDict):
    """
    Debate Subgraph 的状态定义

    用于 Author-Editor 对抗循环子图，跟踪每轮的
    重写内容、编辑反馈和评分。
    """
    # 输入字段
    content: str
    topic: Optional[str]

    # 对抗循环控制
    current_iteration: int
    max_iterations: int
    pass_score: float

    # 当前轮次内容
    author_output: Optional[str]
    editor_feedback: Optional[str]
    editor_score: float

    # 历史记录
    debate_history: Annotated[list[DebateRound], operator.add]

    # 最终结果
    final_content: Optional[str]
    is_passed: bool

    # 消息流
    messages: Annotated[list[BaseMessage], operator.add]

    # 错误处理
    error: Optional[str]
