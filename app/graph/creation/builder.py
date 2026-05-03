"""Creation Graph 构建模块

本模块负责构建和编译 Creation Graph，实现完整的创作流程：
1. PlannerNode 生成大纲
2. interrupt_before 等待用户确认大纲
3. WriterNode 并发撰写章节（Map-Reduce 模式）
4. ReducerNode 合并章节并润色

使用单例模式确保全局只有一个编译后的 Graph 实例。
"""

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.core.logger import get_logger
from app.graph.creation.nodes import (
    planner_node,
    reducer_node,
    writer_node,
)
from app.graph.creation.state import CreationState

logger = get_logger(__name__)


def _route_after_planner(state: CreationState) -> str:
    """PlannerNode 之后的路由函数

    如果有错误，直接结束；否则进入大纲确认中断点。

    Args:
        state: 当前图状态

    Returns:
        str: 下一个节点名称
    """
    if state.get("error"):
        logger.warning("PlannerNode 执行出错，流程结束")
        return END

    # 进入大纲确认中断点
    logger.info("大纲生成完成，等待用户确认")
    return "outline_confirmation"


def _fan_out_writers(state: CreationState) -> list[Send]:
    """扇出 WriterNode 任务

    根据大纲章节数量，创建多个并行的 WriterNode 任务。
    使用 Send API 实现 Map-Reduce 模式。

    Args:
        state: 当前图状态

    Returns:
        list[Send]: Send 对象列表，每个对应一个 WriterNode 任务
    """
    outline = state.get("outline", [])
    existing_sections = state.get("sections", [])

    if not outline:
        logger.warning("大纲为空，无法扇出写作任务")
        return []

    # 计算需要撰写的章节
    remaining_sections = len(outline) - len(existing_sections)

    if remaining_sections <= 0:
        logger.info("所有章节已完成撰写")
        return []

    logger.info(f"扇出 {remaining_sections} 个写作任务")

    # 为每个待撰写章节创建 Send 任务
    sends = []
    for i in range(len(existing_sections), len(outline)):
        # 创建每个 WriterNode 的初始状态
        writer_state: CreationState = {
            "topic": state.get("topic", ""),
            "description": state.get("description"),
            "outline": outline,
            "sections": existing_sections[:i],  # 传递当前已有的章节
            "final_draft": None,
            "messages": [],
            "current_node": f"WriterNode_{i}",
            "error": None,
        }
        sends.append(Send("writer", writer_state))

    return sends


def _route_after_writing(state: CreationState) -> str:
    """WriterNode 之后的路由函数

    检查是否所有章节都已完成撰写，决定是继续写作还是进入合并阶段。

    Args:
        state: 当前图状态

    Returns:
        str: 下一个节点名称或 Send 对象
    """
    if state.get("error"):
        logger.warning("WriterNode 执行出错，流程结束")
        return END

    sections = state.get("sections", [])
    outline = state.get("outline", [])

    # 如果还有未完成的章节，继续扇出写作任务
    if len(sections) < len(outline):
        return "fan_out"

    # 所有章节完成，进入合并阶段
    logger.info("所有章节已完成，进入合并阶段")
    return "reducer"


def _route_after_reducer(state: CreationState) -> str:
    """ReducerNode 之后的路由函数

    检查是否有错误，决定流程走向。

    Args:
        state: 当前图状态

    Returns:
        str: 下一个节点名称
    """
    if state.get("error"):
        logger.warning("ReducerNode 执行出错，流程结束")
        return END

    logger.info("文章合并完成，流程结束")
    return END


def build_creation_graph() -> StateGraph:
    """构建 Creation Graph

    创建并配置创作流程的状态图，包括：
    - 节点：planner, outline_confirmation, writer, reducer
    - 边：条件边和普通边
    - 中断点：大纲确认

    Returns:
        StateGraph: 编译后的 Creation Graph
    """
    logger.info("开始构建 Creation Graph")

    # 创建 StateGraph 实例
    graph = StateGraph(CreationState)

    # ============================================
    # 添加节点
    # ============================================

    # PlannerNode: 生成大纲
    graph.add_node("planner", planner_node)

    # Outline Confirmation: 大纲确认节点（HITL 中断点）
    # 这是一个虚拟节点，实际的用户确认在图外部处理
    graph.add_node("outline_confirmation", lambda state: {
        "current_node": "outline_confirmation",
        "messages": state.get("messages", []),
    })

    # Fan Out: 扇出节点，用于触发并发写作任务
    graph.add_node("fan_out", lambda state: {
        "current_node": "fan_out",
    })

    # WriterNode: 撰写章节
    graph.add_node("writer", writer_node)

    # ReducerNode: 合并章节
    graph.add_node("reducer", reducer_node)

    # ============================================
    # 定义边
    # ============================================

    # START -> PlannerNode
    graph.add_edge(START, "planner")

    # PlannerNode -> 条件路由（错误检查 / 大纲确认）
    graph.add_conditional_edges(
        "planner",
        _route_after_planner,
        {
            "outline_confirmation": "outline_confirmation",
            END: END,
        },
    )

    # Outline Confirmation -> Fan Out（用户确认后）
    graph.add_edge("outline_confirmation", "fan_out")

    # Fan Out -> 条件路由（扇出写作 / 进入合并）
    graph.add_conditional_edges(
        "fan_out",
        _route_after_writing,
        {
            "fan_out": "fan_out",  # 继续扇出
            "reducer": "reducer",
            END: END,
        },
    )

    # WriterNode -> 条件路由（继续写作 / 进入合并）
    graph.add_conditional_edges(
        "writer",
        _route_after_writing,
        {
            "fan_out": "fan_out",
            "reducer": "reducer",
            END: END,
        },
    )

    # ReducerNode -> END
    graph.add_conditional_edges(
        "reducer",
        _route_after_reducer,
        {
            END: END,
        },
    )

    logger.info("Creation Graph 构建完成")
    return graph


@lru_cache
def get_creation_graph() -> StateGraph:
    """获取 Creation Graph 单例

    使用 lru_cache 确保全局只有一个编译后的 Graph 实例。

    Returns:
        StateGraph: 编译后的 Creation Graph
    """
    graph = build_creation_graph()

    # 编译图，配置 interrupt_before 在大纲确认点暂停
    compiled_graph = graph.compile(
        interrupt_before=["outline_confirmation"],
    )

    logger.info("Creation Graph 编译完成，已配置 interrupt_before")
    return compiled_graph


# 导出便捷函数
creation_graph = get_creation_graph
