"""
Polishing Graph 状态定义

本模块定义润色流程的状态结构，使用 TypedDict 确保类型安全。
包含两个状态类：
- PolishingState: 主图状态，跟踪整个润色流程
- DebateState: 子图状态，用于 Author-Editor 对抗循环
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
