"""Creation Graph 构建模块

本模块负责构建和编译 Creation Graph，实现完整的创作流程：
1. PlannerNode 生成大纲
2. interrupt_before 等待用户确认大纲
3. WriterNode 并发撰写章节（Map-Reduce 模式）
4. ReducerNode 合并章节并润色

图结构构建与编译分离：
- build_creation_graph() 构建未编译的 StateGraph
- get_creation_graph(checkpointer) 编译图并注入 Checkpointer
"""

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
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

    根据大纲章节数量，为每个章节创建一个并行的 WriterNode 任务。
    使用 Send API 实现 Map-Reduce 模式。
    每个 writer 独立工作，通过 sections 的 operator.add reducer 自动合并结果。

    Args:
        state: 当前图状态

    Returns:
        list[Send]: Send 对象列表，每个对应一个 WriterNode 任务
    """
    outline = state.get("outline", [])

    if not outline:
        logger.warning("大纲为空，无法扇出写作任务")
        return []

    logger.info(f"扇出 {len(outline)} 个写作任务")

    # 为每个章节创建 Send 任务，传入该章节的索引信息
    sends = []
    for i in range(len(outline)):
        writer_state: CreationState = {
            "topic": state.get("topic", ""),
            "description": state.get("description"),
            "outline": outline,
            "sections": [{"title": outline[j]["title"], "content": "", "index": j} for j in range(i)],
            "final_draft": None,
            "messages": [],
            "current_node": f"WriterNode_{i}",
            "error": None,
        }
        sends.append(Send("writer", writer_state))

    return sends


def _route_after_writing(state: CreationState) -> str:
    """WriterNode 之后的路由函数

    所有章节通过 Send 并发执行，完成后统一进入合并阶段。

    Args:
        state: 当前图状态

    Returns:
        str: 下一个节点名称
    """
    if state.get("error"):
        logger.warning("WriterNode 执行出错，流程结束")
        return END

    # Send 并发模式下，所有 writer 完成后直接进入合并
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

    流程：planner → (interrupt) outline_confirmation → fan_out writers → reducer → END

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

    # Outline Confirmation -> 扇出 WriterNode（通过 Send 并发）
    graph.add_conditional_edges(
        "outline_confirmation",
        _fan_out_writers,
    )

    # WriterNode -> 条件路由（完成 → 合并）
    graph.add_conditional_edges(
        "writer",
        _route_after_writing,
        {
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


def get_creation_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> StateGraph:
    """编译并返回 Creation Graph

    每次调用都会重新编译图。服务层应缓存返回的编译后图实例。
    编译时配置 interrupt_before=["outline_confirmation"] 以支持 HITL。

    Args:
        checkpointer: 可选的 Checkpointer 实例，用于状态持久化和中断恢复。
            传入 None 时图不支持状态持久化（仅适用于测试场景）。

    Returns:
        StateGraph: 编译后的 Creation Graph
    """
    graph = build_creation_graph()

    compiled_graph = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["outline_confirmation"],
    )

    logger.info(
        f"Creation Graph 编译完成 - "
        f"checkpointer: {'已注入' if checkpointer else '未注入'}"
    )
    return compiled_graph


def build_compiled_creation_graph() -> StateGraph:
    """构建并编译 Creation Graph（无参数版本，供 LangGraph CLI 使用）

    LangGraph CLI 要求图入口为无参数可调用对象。
    该函数内部构建并编译图，不注入 checkpointer（由 CLI 运行时自动管理）。

    Returns:
        StateGraph: 编译后的 Creation Graph
    """
    return get_creation_graph(checkpointer=None)
