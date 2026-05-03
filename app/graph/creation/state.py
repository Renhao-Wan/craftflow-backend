"""
Creation Graph 状态定义

本模块定义创作流程的状态结构，使用 TypedDict 确保类型安全。
sections 字段配置了 operator.add 作为 Reducer，支持并发节点的结果合并。
"""

import operator
from typing import Annotated, Optional, TypedDict

from langchain_core.messages import BaseMessage


class SectionContent(TypedDict):
    """单个章节内容结构"""
    title: str
    content: str
    index: int


class OutlineItem(TypedDict):
    """大纲条目结构"""
    title: str
    summary: str


class CreationState(TypedDict):
    """
    Creation Graph 的状态定义

    用于跟踪整个创作流程的状态，包括主题、大纲、章节内容和最终草稿。
    sections 字段使用 operator.add 作为 Reducer，支持 Map-Reduce 模式下的
    并发章节生成与自动合并。
    """
    topic: str
    description: Optional[str]
    outline: list[OutlineItem]
    sections: Annotated[list[SectionContent], operator.add]
    final_draft: Optional[str]
    messages: Annotated[list[BaseMessage], operator.add]
    current_node: Optional[str]
    error: Optional[str]
