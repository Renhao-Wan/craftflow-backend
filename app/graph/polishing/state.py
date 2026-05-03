"""
Polishing Graph 状态定义

本模块定义润色流程的主状态结构，使用 TypedDict 确保类型安全。
"""

import operator
from typing import Annotated, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage


class ScoreDetail(TypedDict):
    """评分详情结构"""
    dimension: str
    score: float
    comment: str


class DebateRound(TypedDict):
    """对抗轮次记录"""
    round_number: int
    author_content: str
    editor_feedback: str
    editor_score: float


class PolishingState(TypedDict):
    """
    Polishing Graph 的主状态定义

    用于跟踪整个润色流程，包括输入内容、润色模式、
    中间结果和最终输出。
    """
    # 输入字段
    content: str
    mode: Literal[1, 2, 3]

    # 流程控制
    current_node: Optional[str]
    error: Optional[str]

    # 中间结果
    formatted_content: Optional[str]
    fact_check_result: Optional[str]
    debate_history: list[DebateRound]

    # 最终输出
    final_content: Optional[str]
    scores: list[ScoreDetail]
    overall_score: Optional[float]

    # 消息流
    messages: Annotated[list[BaseMessage], operator.add]
