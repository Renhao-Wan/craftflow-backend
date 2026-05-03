"""Debate Subgraph - Author-Editor 对抗循环子图

本模块实现 Author-Editor 对抗循环的独立子图：
- author_node: 根据编辑反馈重写内容
- editor_node: 对内容进行多维度评分
- increment_iteration_node: 递增迭代计数器
- finalize_debate_node: 设置最终输出内容

循环终止条件：
- 评分达到 pass_score 阈值
- 迭代次数达到 max_iterations 上限
"""

from functools import lru_cache

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from app.core.logger import get_logger
from app.graph.polishing.nodes import (
    author_node,
    editor_node,
    should_continue_debate,
)
from app.graph.polishing.state import DebateState

logger = get_logger(__name__)


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
# 图构建
# ============================================


def _build_debate_graph() -> StateGraph:
    """构建 Debate Subgraph

    图结构：
        START -> author -> editor -> increment_iteration -> should_continue
            ├─ "author" -> author  (继续下一轮)
            └─ "end" -> finalize -> END

    Returns:
        StateGraph: 编译前的图实例
    """
    graph = StateGraph(DebateState)

    # 添加节点
    graph.add_node("author", author_node)
    graph.add_node("editor", editor_node)
    graph.add_node("increment_iteration", increment_iteration_node)
    graph.add_node("finalize", finalize_debate_node)

    # 定义边
    graph.set_entry_point("author")
    graph.add_edge("author", "editor")
    graph.add_edge("editor", "increment_iteration")

    # 条件边：根据评分和迭代次数决定继续或结束
    graph.add_conditional_edges(
        "increment_iteration",
        should_continue_debate,
        {
            "author": "author",
            "end": "finalize",
        },
    )

    graph.add_edge("finalize", END)

    return graph


@lru_cache(maxsize=1)
def get_debate_graph() -> StateGraph:
    """获取编译后的 Debate Subgraph 单例

    使用 lru_cache 确保全局只有一个编译后的图实例。

    Returns:
        StateGraph: 编译后的 Debate Subgraph
    """
    logger.info("编译 Debate Subgraph")
    graph = _build_debate_graph()
    return graph.compile()
