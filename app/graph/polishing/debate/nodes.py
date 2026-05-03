"""Debate Subgraph 节点实现

本模块实现 Author-Editor 对抗循环中的核心节点：
- author_node: 根据编辑反馈重写内容
- editor_node: 对内容进行多维度评分
- increment_iteration_node: 递增迭代计数器
- finalize_debate_node: 设置最终输出内容
"""

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.logger import get_logger
from app.graph.common.llm_factory import get_default_llm, get_editor_llm
from app.graph.polishing.debate.prompts import (
    AUTHOR_HUMAN_PROMPT,
    AUTHOR_SYSTEM_PROMPT,
    EDITOR_HUMAN_PROMPT,
    EDITOR_SYSTEM_PROMPT,
    format_editor_feedback,
)
from app.graph.polishing.debate.state import DebateState
from app.graph.polishing.state import DebateRound

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


# ============================================
# AuthorNode
# ============================================


async def author_node(state: DebateState) -> dict[str, Any]:
    """AuthorNode: 重写内容

    根据编辑反馈对文章进行深度润色和重写。

    Args:
        state: 当前图状态（DebateState）

    Returns:
        dict: 状态增量更新
    """
    content = state.get("content", "")
    editor_feedback = state.get("editor_feedback", "")
    editor_score = state.get("editor_score", 0)

    logger.info(f"AuthorNode 开始执行 - 当前评分: {editor_score}")

    try:
        llm = get_default_llm()

        # 如果没有编辑反馈（第一轮），使用默认提示
        if not editor_feedback:
            editor_feedback = "这是第一轮润色，请对文章进行全面优化。"

        human_message = AUTHOR_HUMAN_PROMPT.format(
            content=content,
            editor_feedback=editor_feedback,
            editor_score=editor_score,
        )

        messages = [
            SystemMessage(content=AUTHOR_SYSTEM_PROMPT),
            HumanMessage(content=human_message),
        ]

        response = await llm.ainvoke(messages)
        author_output = response.content if isinstance(response.content, str) else str(response.content)

        logger.info("AuthorNode 重写完成")

        return {
            "author_output": author_output,
            "messages": [AIMessage(content="文章重写完成")],
        }

    except Exception as e:
        logger.error(f"AuthorNode 执行失败: {str(e)}")
        return {
            "error": f"文章重写失败: {str(e)}",
            "messages": [AIMessage(content=f"文章重写失败: {str(e)}")],
        }


# ============================================
# EditorNode
# ============================================


async def editor_node(state: DebateState) -> dict[str, Any]:
    """EditorNode: 评分与反馈

    对文章进行多维度评估和打分，提供改进建议。

    Args:
        state: 当前图状态（DebateState）

    Returns:
        dict: 状态增量更新
    """
    author_output = state.get("author_output", "")
    content = author_output or state.get("content", "")
    current_iteration = state.get("current_iteration", 0)

    logger.info(f"EditorNode 开始执行 - 第 {current_iteration} 轮评估")

    try:
        llm = get_editor_llm()  # 使用更低温度的 LLM

        human_message = EDITOR_HUMAN_PROMPT.format(
            content=content,
            iteration=current_iteration,
        )

        messages = [
            SystemMessage(content=EDITOR_SYSTEM_PROMPT),
            HumanMessage(content=human_message),
        ]

        response = await llm.ainvoke(messages)
        response_content = response.content if isinstance(response.content, str) else str(response.content)

        # 解析评估结果
        result = _extract_json_from_response(response_content)
        if result:
            total_score = result.get("total_score", 0)
            feedback_text = format_editor_feedback(result)

            # 构建对抗轮次记录
            debate_round: DebateRound = {
                "round_number": current_iteration,
                "author_content": content[:500],  # 存储摘要
                "editor_feedback": feedback_text,
                "editor_score": total_score,
            }

            logger.info(f"评估完成，总分: {total_score}/100")

            return {
                "editor_feedback": feedback_text,
                "editor_score": total_score,
                "debate_history": [debate_round],
                "is_passed": total_score >= state.get("pass_score", 90),
                "messages": [AIMessage(content=f"第 {current_iteration} 轮评估完成，评分: {total_score}/100")],
            }
        else:
            logger.warning("评估结果解析失败，使用默认分数")
            return {
                "editor_feedback": response_content,
                "editor_score": 70,
                "is_passed": False,
                "messages": [AIMessage(content="评估完成，但结果格式异常")],
            }

    except Exception as e:
        logger.error(f"EditorNode 执行失败: {str(e)}")
        return {
            "error": f"评估失败: {str(e)}",
            "editor_score": 0,
            "is_passed": False,
            "messages": [AIMessage(content=f"评估失败: {str(e)}")],
        }


# ============================================
# 辅助节点
# ============================================


async def increment_iteration_node(state: DebateState) -> dict:
    """递增迭代计数器

    在每轮 editor 评估完成后调用，更新 current_iteration。

    Args:
        state: 当前图状态

    Returns:
        dict: 包含递增后的 current_iteration
    """
    current = state.get("current_iteration", 0)
    new_iteration = current + 1
    logger.info(f"迭代计数递增: {current} -> {new_iteration}")

    return {
        "current_iteration": new_iteration,
        "messages": [AIMessage(content=f"第 {new_iteration} 轮对抗完成")],
    }


async def finalize_debate_node(state: DebateState) -> dict:
    """终结节点：设置最终输出内容

    对抗循环结束时，将最后一次 author 的输出设为 final_content。

    Args:
        state: 当前图状态

    Returns:
        dict: 包含 final_content
    """
    # 优先使用 author_output，回退到原始 content
    final_content = state.get("author_output") or state.get("content", "")
    is_passed = state.get("is_passed", False)
    editor_score = state.get("editor_score", 0)
    current_iteration = state.get("current_iteration", 0)

    logger.info(
        f"对抗循环结束 - 通过: {is_passed}, "
        f"最终评分: {editor_score}, 总轮次: {current_iteration}"
    )

    return {
        "final_content": final_content,
        "messages": [
            AIMessage(
                content=(
                    f"对抗审查完成 - 最终评分: {editor_score}/100, "
                    f"轮次: {current_iteration}, 通过: {is_passed}"
                )
            )
        ],
    }


# ============================================
# 条件边函数
# ============================================


def should_continue_debate(state: DebateState) -> str:
    """判断是否继续对抗循环

    Args:
        state: 当前图状态

    Returns:
        str: "author"（继续）或 "end"（结束）
    """
    # 检查是否通过评分
    if state.get("is_passed", False):
        logger.info("评分达标，结束对抗循环")
        return "end"

    # 检查是否达到最大迭代次数
    current_iteration = state.get("current_iteration", 0)
    max_iterations = state.get("max_iterations", 3)

    if current_iteration >= max_iterations:
        logger.info("达到最大迭代次数，结束对抗循环")
        return "end"

    # 继续下一轮
    logger.info(f"继续第 {current_iteration + 1} 轮对抗")
    return "author"
