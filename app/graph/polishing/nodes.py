"""Polishing Graph 节点实现

本模块实现润色流程中的核心节点：
- router_node: 路由决策
- formatter_node: 格式化内容
- fact_checker_node: 事实核查

AuthorNode、EditorNode 等对抗循环节点位于 debate/nodes.py。
"""

import json
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.core.logger import get_logger
from app.graph.common.llm_factory import get_default_llm
from app.graph.polishing.prompts import (
    FACT_CHECKER_HUMAN_PROMPT,
    FACT_CHECKER_SYSTEM_PROMPT,
    FORMATTER_HUMAN_PROMPT,
    FORMATTER_SYSTEM_PROMPT,
    ROUTER_HUMAN_PROMPT,
    ROUTER_SYSTEM_PROMPT,
    format_fact_check_result,
)
from app.graph.polishing.state import PolishingState
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
