"""Polishing Graph 节点实现

本模块实现润色流程中的核心节点：
- router_node: 路由决策
- formatter_node: 格式化内容
- fact_checker_node: 事实核查
- author_node: 重写内容
- editor_node: 评分与反馈
"""

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.logger import get_logger
from app.graph.common.llm_factory import get_default_llm, get_editor_llm
from app.graph.polishing.prompts import (
    AUTHOR_HUMAN_PROMPT,
    AUTHOR_SYSTEM_PROMPT,
    EDITOR_HUMAN_PROMPT,
    EDITOR_SYSTEM_PROMPT,
    FACT_CHECKER_HUMAN_PROMPT,
    FACT_CHECKER_SYSTEM_PROMPT,
    FORMATTER_HUMAN_PROMPT,
    FORMATTER_SYSTEM_PROMPT,
    ROUTER_HUMAN_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    format_editor_feedback,
    format_fact_check_result,
)
from app.graph.polishing.state import (
    DebateRound,
    DebateState,
    PolishingState,
    ScoreDetail,
)
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


# ============================================
# RouterNode
# ============================================


async def router_node(state: PolishingState) -> dict[str, Any]:
    """RouterNode: 路由决策

    分析文章内容，决定使用哪种润色模式。
    如果用户已指定模式，则直接使用用户指定的模式。

    Args:
        state: 当前图状态

    Returns:
        dict: 状态增量更新
    """
    content = state.get("content", "")
    mode = state.get("mode", 2)

    logger.info(f"RouterNode 开始执行 - 指定模式: {mode}")

    # 如果用户已指定模式（非默认值），直接使用
    if mode in [1, 2, 3]:
        logger.info(f"使用用户指定的模式: {mode}")
        return {
            "mode": mode,
            "current_node": "router",
            "messages": [AIMessage(content=f"已选择润色模式: {mode}")],
        }

    # 使用 LLM 分析并推荐模式
    try:
        llm = get_default_llm()

        human_message = ROUTER_HUMAN_PROMPT.format(content=content[:2000])  # 限制长度

        messages = [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=human_message),
        ]

        response = await llm.ainvoke(messages)
        response_content = response.content if isinstance(response.content, str) else str(response.content)

        # 解析推荐结果
        result = _extract_json_from_response(response_content)
        if result and "recommended_mode" in result:
            recommended_mode = result["recommended_mode"]
            reason = result.get("reason", "")
            logger.info(f"推荐模式: {mode}，理由: {reason}")

            return {
                "mode": recommended_mode,
                "current_node": "router",
                "messages": [AIMessage(content=f"推荐润色模式: {recommended_mode}，理由: {reason}")],
            }

    except Exception as e:
        logger.warning(f"模式推荐失败，使用默认模式 2: {str(e)}")

    # 默认使用模式 2
    return {
        "mode": 2,
        "current_node": "router",
        "messages": [AIMessage(content="使用默认润色模式: 2（专家对抗审查）")],
    }


# ============================================
# FormatterNode
# ============================================


async def formatter_node(state: PolishingState) -> dict[str, Any]:
    """FormatterNode: 格式化内容

    对文章进行格式化处理，确保 Markdown 格式规范。

    Args:
        state: 当前图状态

    Returns:
        dict: 状态增量更新
    """
    content = state.get("content", "")

    logger.info("FormatterNode 开始执行")

    try:
        llm = get_default_llm()

        human_message = FORMATTER_HUMAN_PROMPT.format(content=content)

        messages = [
            SystemMessage(content=FORMATTER_SYSTEM_PROMPT),
            HumanMessage(content=human_message),
        ]

        response = await llm.ainvoke(messages)
        formatted_content = response.content if isinstance(response.content, str) else str(response.content)

        logger.info("格式化完成")

        return {
            "formatted_content": formatted_content,
            "final_content": formatted_content,
            "current_node": "formatter",
            "messages": [AIMessage(content="文章格式化完成")],
        }

    except Exception as e:
        logger.error(f"FormatterNode 执行失败: {str(e)}")
        return {
            "error": f"格式化失败: {str(e)}",
            "current_node": "formatter",
            "messages": [AIMessage(content=f"格式化失败: {str(e)}")],
        }


# ============================================
# FactCheckerNode
# ============================================


async def fact_checker_node(state: PolishingState) -> dict[str, Any]:
    """FactCheckerNode: 事实核查

    对文章中的事实性内容进行核查，使用搜索工具验证关键事实。

    Args:
        state: 当前图状态

    Returns:
        dict: 状态增量更新
    """
    content = state.get("content", "")

    logger.info("FactCheckerNode 开始执行")

    try:
        llm = get_default_llm()
        llm_with_tools = llm.bind_tools(SEARCH_TOOLS)

        human_message = FACT_CHECKER_HUMAN_PROMPT.format(content=content)

        messages = [
            SystemMessage(content=FACT_CHECKER_SYSTEM_PROMPT),
            HumanMessage(content=human_message),
        ]

        response = await llm_with_tools.ainvoke(messages)
        response_content = response.content if isinstance(response.content, str) else str(response.content)

        # 解析核查结果
        result = _extract_json_from_response(response_content)
        if result:
            fact_check_text = format_fact_check_result(result)
            logger.info(f"事实核查完成，准确性: {result.get('overall_accuracy', 'unknown')}")

            return {
                "fact_check_result": fact_check_text,
                "current_node": "fact_checker",
                "messages": [AIMessage(content=f"事实核查完成：\n\n{fact_check_text}")],
            }
        else:
            logger.warning("事实核查结果解析失败")
            return {
                "fact_check_result": response_content,
                "current_node": "fact_checker",
                "messages": [AIMessage(content="事实核查完成，但结果格式异常")],
            }

    except Exception as e:
        logger.error(f"FactCheckerNode 执行失败: {str(e)}")
        return {
            "error": f"事实核查失败: {str(e)}",
            "current_node": "fact_checker",
            "messages": [AIMessage(content=f"事实核查失败: {str(e)}")],
        }


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
# 条件边函数
# ============================================


def route_by_mode(state: PolishingState) -> str:
    """根据润色模式路由

    Args:
        state: 当前图状态

    Returns:
        str: 下一个节点名称
    """
    mode = state.get("mode", 2)

    if mode == 1:
        return "formatter"
    elif mode == 2:
        return "author"
    elif mode == 3:
        return "fact_checker"
    else:
        return "author"  # 默认使用对抗审查


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
