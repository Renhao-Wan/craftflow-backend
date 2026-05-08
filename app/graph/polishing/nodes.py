"""Polishing Graph 节点实现

本模块实现润色流程中的核心节点：
- router_node: 路由决策
- formatter_node: 格式化内容
- fact_checker_node: 事实核查

AuthorNode、EditorNode 等对抗循环节点位于 debate/nodes.py。
"""

import asyncio
import json
import re
from typing import Any, Callable, Awaitable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

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

# ============================================
# 进度回调注册表（service 层注册，node 层调用）
# ============================================

_ProgressCallback = Callable[[str, str, float], Awaitable[None]]
_progress_callbacks: dict[str, _ProgressCallback] = {}


def register_progress_callback(task_id: str, callback: _ProgressCallback) -> None:
    """注册任务的进度回调（service 层调用）"""
    _progress_callbacks[task_id] = callback


def unregister_progress_callback(task_id: str) -> None:
    """注销任务的进度回调"""
    _progress_callbacks.pop(task_id, None)


async def _report_progress(task_id: str, node: str, label: str, progress: float) -> None:
    """报告中间进度（node 层调用）"""
    cb = _progress_callbacks.get(task_id)
    if cb:
        try:
            await cb(node, label, progress)
        except Exception as e:
            logger.warning(f"进度回调失败: {e}")


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


MAX_TOOL_ROUNDS = 3


async def fact_checker_node(state: PolishingState) -> dict[str, Any]:
    """FactCheckerNode: 事实核查（含搜索工具 agent loop）

    对文章中的事实性内容进行核查，通过 agent loop 调用搜索工具验证关键事实。
    核查完成后判断是否需要进入修正流程。

    Args:
        state: 当前图状态

    Returns:
        dict: 状态增量更新（含 needs_revision 标记）
    """
    content = state.get("content", "")
    task_id = state.get("task_id", "")
    mode = state.get("mode", 3)

    logger.info("FactCheckerNode 开始执行")

    # 进度范围：mode 3 为 10%-50%（后续 debate）或 10%-90%（high 直接结束）
    fc_start = 10.0
    fc_end = 50.0  # 先按 50% 计算，最终由 _calculate_fact_checker_progress 调整

    await _report_progress(task_id, "fact_checker", "事实核查", fc_start)

    try:
        llm = get_default_llm()
        llm_with_tools = llm.bind_tools(SEARCH_TOOLS)

        human_message = FACT_CHECKER_HUMAN_PROMPT.format(content=content)

        messages: list = [
            SystemMessage(content=FACT_CHECKER_SYSTEM_PROMPT),
            HumanMessage(content=human_message),
        ]

        # Agent loop: LLM → 执行 tool_calls → 结果喂回 LLM → 重复
        tool_map = {t.name: t for t in SEARCH_TOOLS}
        final_response = None

        for round_num in range(MAX_TOOL_ROUNDS + 1):
            response = await llm_with_tools.ainvoke(messages)

            # 调试日志：记录 LLM 响应
            logger.debug(
                f"LLM 响应 - 轮次: {round_num}, "
                f"has_tool_calls: {bool(response.tool_calls)}, "
                f"tool_calls_count: {len(response.tool_calls) if response.tool_calls else 0}, "
                f"content_preview: {str(response.content)[:200]}"
            )

            # 没有工具调用，这是最终响应
            if not response.tool_calls:
                final_response = response
                logger.info(f"Agent loop 结束，共 {round_num} 轮工具调用")
                break

            # 有工具调用，执行工具
            messages.append(response)  # 把 AI 响应（含 tool_calls）加入上下文
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_id = tc["id"]

                logger.info(f"执行搜索工具: {tool_name}({tool_args})")

                tool_fn = tool_map.get(tool_name)
                if tool_fn:
                    try:
                        result = await asyncio.wait_for(
                            tool_fn.ainvoke(tool_args), timeout=30
                        )
                        tool_result = str(result) if not isinstance(result, str) else result
                    except asyncio.TimeoutError:
                        tool_result = f"工具执行超时（30秒）: {tool_name}"
                        logger.warning(f"工具 {tool_name} 执行超时")
                    except Exception as e:
                        tool_result = f"工具执行失败: {str(e)}"
                        logger.warning(f"工具 {tool_name} 执行失败: {e}")
                else:
                    tool_result = f"未知工具: {tool_name}"
                    logger.warning(f"未知工具: {tool_name}")

                messages.append(ToolMessage(
                    content=tool_result,
                    tool_call_id=tool_id,
                ))

            # 报告中间进度
            round_progress = fc_start + (round_num + 1) / (MAX_TOOL_ROUNDS + 1) * (fc_end - fc_start)
            await _report_progress(task_id, "fact_checker", f"事实核查（第 {round_num + 1} 轮搜索）", round_progress)
            logger.debug(f"Agent loop 第 {round_num + 1} 轮完成")
        else:
            # 达到最大轮次，再次调用 LLM 获取最终文本响应（不含工具调用）
            logger.warning(f"Agent loop 达到最大轮次 {MAX_TOOL_ROUNDS}，获取最终响应")
            final_response = await llm.ainvoke(messages)

        # 使用最终响应的内容
        response_content = (
            final_response.content if isinstance(final_response.content, str)
            else str(final_response.content)
        )

        # 报告最终分析阶段进度
        await _report_progress(task_id, "fact_checker", "正在生成核查报告", fc_end)

        # 解析最终核查结果
        result = _extract_json_from_response(response_content)
        if result:
            fact_check_text = format_fact_check_result(result)
            issues = result.get("issues", [])
            overall_accuracy = result.get("overall_accuracy", "unknown")

            # 只要不是 high 就进入修正流程
            needs_revision = overall_accuracy != "high"

            logger.info(
                f"事实核查完成 - 准确性: {overall_accuracy}, "
                f"问题数: {len(issues)}, 需要修正: {needs_revision}"
            )

            return {
                "fact_check_result": fact_check_text,
                "needs_revision": needs_revision,
                "current_node": "fact_checker",
                "messages": [AIMessage(
                    content=f"事实核查完成，发现 {len(issues)} 个问题"
                    if needs_revision
                    else "事实核查完成，未发现明显问题"
                )],
            }
        else:
            logger.warning("事实核查结果解析失败")
            return {
                "fact_check_result": response_content,
                "needs_revision": False,
                "current_node": "fact_checker",
                "messages": [AIMessage(content="事实核查完成，但结果格式异常")],
            }

    except Exception as e:
        logger.error(f"FactCheckerNode 执行失败: {str(e)}")
        return {
            "error": f"事实核查失败: {str(e)}",
            "needs_revision": False,
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


def route_after_fact_check(state: PolishingState) -> str:
    """事实核查后路由

    根据 needs_revision 标记决定是否进入修正流程。
    needs_revision 由 fact_checker_node 根据 overall_accuracy 设置：
    - overall_accuracy == "high" → needs_revision = False → END
    - overall_accuracy != "high" → needs_revision = True → debate

    Args:
        state: 当前图状态

    Returns:
        str: "debate"（需要修正）或 "end"（无需修正）
    """
    needs_revision = state.get("needs_revision", False)

    if needs_revision:
        logger.info("核查发现问题，进入修正流程")
        return "debate"
    else:
        logger.info("核查准确性为 high，无需修正")
        return "end"
