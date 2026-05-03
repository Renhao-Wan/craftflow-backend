"""Creation Graph 节点实现

本模块实现创作流程中的核心节点：
- planner_node: 生成结构化大纲
- writer_node: 撰写单个章节（支持并发）
- reducer_node: 合并章节并润色过渡段
"""

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.logger import get_logger
from app.graph.common.llm_factory import get_default_llm
from app.graph.creation.prompts import (
    PLANNER_HUMAN_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    REDUCER_HUMAN_PROMPT,
    REDUCER_SYSTEM_PROMPT,
    WRITER_HUMAN_PROMPT,
    WRITER_SYSTEM_PROMPT,
    format_outline_for_display,
    format_sections_for_reducer,
)
from app.graph.creation.state import CreationState, OutlineItem, SectionContent
from app.graph.tools.search import SEARCH_TOOLS

logger = get_logger(__name__)


def _extract_json_from_response(text: str) -> dict[str, Any] | None:
    """从 LLM 响应中提取 JSON 内容

    Args:
        text: LLM 响应文本

    Returns:
        dict | None: 解析后的 JSON 字典，解析失败返回 None
    """
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    json_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
    match = re.search(json_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试查找 JSON 对象
    json_object_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
    match = re.search(json_object_pattern, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


async def planner_node(state: CreationState) -> dict[str, Any]:
    """PlannerNode: 生成结构化大纲

    根据用户提供的主题和描述，调用 LLM 生成文章大纲。
    支持绑定搜索工具获取最新信息。

    Args:
        state: 当前图状态，包含 topic 和 description

    Returns:
        dict: 状态增量更新，包含 outline 和 messages
    """
    logger.info(f"PlannerNode 开始执行 - 主题: {state.get('topic', '未指定')}")

    try:
        # 获取 LLM 实例并绑定搜索工具
        llm = get_default_llm()
        llm_with_tools = llm.bind_tools(SEARCH_TOOLS)

        # 构建 Prompt
        description = state.get("description", "")
        description_section = f"**补充描述**：{description}" if description else ""

        human_message = PLANNER_HUMAN_PROMPT.format(
            topic=state.get("topic", ""),
            description_section=description_section,
        )

        # 调用 LLM
        messages = [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=human_message),
        ]

        response = await llm_with_tools.ainvoke(messages)
        response_content = response.content if isinstance(response.content, str) else str(response.content)

        # 解析大纲
        outline_data = _extract_json_from_response(response_content)

        if outline_data and "outline" in outline_data:
            outline: list[OutlineItem] = outline_data["outline"]
            logger.info(f"大纲生成成功，共 {len(outline)} 个章节")

            # 返回状态更新
            return {
                "outline": outline,
                "messages": [AIMessage(content=f"已生成大纲：\n\n{format_outline_for_display(outline)}")],
                "current_node": "PlannerNode",
            }
        else:
            # 解析失败，使用默认大纲
            logger.warning("大纲 JSON 解析失败，使用默认结构")
            default_outline: list[OutlineItem] = [
                {"title": "引言", "summary": "介绍主题背景和核心概念"},
                {"title": "核心内容", "summary": "详细阐述主题的关键要点"},
                {"title": "实践应用", "summary": "讨论实际应用场景和案例"},
                {"title": "总结", "summary": "归纳核心观点和未来展望"},
            ]

            return {
                "outline": default_outline,
                "messages": [AIMessage(content="大纲生成遇到解析问题，已使用默认大纲结构")],
                "current_node": "PlannerNode",
            }

    except Exception as e:
        logger.error(f"PlannerNode 执行失败: {str(e)}")
        return {
            "error": f"大纲生成失败: {str(e)}",
            "messages": [AIMessage(content=f"大纲生成失败: {str(e)}")],
            "current_node": "PlannerNode",
        }


async def writer_node(state: CreationState) -> dict[str, Any]:
    """WriterNode: 撰写单个章节

    根据大纲中的章节信息，调用 LLM 生成单个章节的内容。
    此节点设计为可并发执行多个实例。

    Args:
        state: 当前图状态，包含 outline 和当前章节索引

    Returns:
        dict: 状态增量更新，包含 sections（追加模式）
    """
    # 获取当前需要撰写的章节索引
    # 通过 state 中的 current_section_index 或已生成的 sections 数量确定
    existing_sections = state.get("sections", [])
    outline = state.get("outline", [])
    current_index = len(existing_sections)

    if current_index >= len(outline):
        logger.warning("所有章节已撰写完成")
        return {"current_node": "WriterNode"}

    # 获取当前章节信息
    section_info = outline[current_index]
    section_title = section_info.get("title", f"第 {current_index + 1} 章")
    section_summary = section_info.get("summary", "")

    logger.info(f"WriterNode 开始执行 - 撰写第 {current_index + 1} 章: {section_title}")

    try:
        # 获取 LLM 实例
        llm = get_default_llm()

        # 构建 Prompt
        human_message = WRITER_HUMAN_PROMPT.format(
            section_title=section_title,
            section_summary=section_summary,
            topic=state.get("topic", ""),
            section_index=current_index + 1,
            total_sections=len(outline),
        )

        # 调用 LLM
        messages = [
            SystemMessage(content=WRITER_SYSTEM_PROMPT),
            HumanMessage(content=human_message),
        ]

        response = await llm.ainvoke(messages)
        content = response.content if isinstance(response.content, str) else str(response.content)

        # 构建章节内容
        section_content: SectionContent = {
            "title": section_title,
            "content": content,
            "index": current_index,
        }

        logger.info(f"第 {current_index + 1} 章撰写完成: {section_title}")

        # 返回状态更新（使用 add reducer 追加）
        return {
            "sections": [section_content],
            "messages": [AIMessage(content=f"已完成第 {current_index + 1} 章：{section_title}")],
            "current_node": "WriterNode",
        }

    except Exception as e:
        logger.error(f"WriterNode 执行失败 - 第 {current_index + 1} 章: {str(e)}")
        return {
            "error": f"第 {current_index + 1} 章撰写失败: {str(e)}",
            "messages": [AIMessage(content=f"第 {current_index + 1} 章撰写失败: {str(e)}")],
            "current_node": "WriterNode",
        }


async def reducer_node(state: CreationState) -> dict[str, Any]:
    """ReducerNode: 合并章节并润色过渡段

    将所有独立撰写的章节合并成一篇完整的文章，添加引言、过渡段落和总结。

    Args:
        state: 当前图状态，包含 sections 和 topic

    Returns:
        dict: 状态增量更新，包含 final_draft
    """
    sections = state.get("sections", [])
    topic = state.get("topic", "未命名主题")

    logger.info(f"ReducerNode 开始执行 - 合并 {len(sections)} 个章节")

    if not sections:
        logger.warning("没有可合并的章节")
        return {
            "final_draft": "",
            "messages": [AIMessage(content="没有可合并的章节内容")],
            "current_node": "ReducerNode",
        }

    try:
        # 获取 LLM 实例
        llm = get_default_llm()

        # 格式化章节内容
        sections_content = format_sections_for_reducer(sections)

        # 构建 Prompt
        human_message = REDUCER_HUMAN_PROMPT.format(
            topic=topic,
            sections_content=sections_content,
        )

        # 调用 LLM
        messages = [
            SystemMessage(content=REDUCER_SYSTEM_PROMPT),
            HumanMessage(content=human_message),
        ]

        response = await llm.ainvoke(messages)
        final_draft = response.content if isinstance(response.content, str) else str(response.content)

        logger.info("文章合并完成")

        # 返回状态更新
        return {
            "final_draft": final_draft,
            "messages": [AIMessage(content="文章合并和润色完成")],
            "current_node": "ReducerNode",
        }

    except Exception as e:
        logger.error(f"ReducerNode 执行失败: {str(e)}")
        return {
            "error": f"文章合并失败: {str(e)}",
            "messages": [AIMessage(content=f"文章合并失败: {str(e)}")],
            "current_node": "ReducerNode",
        }
