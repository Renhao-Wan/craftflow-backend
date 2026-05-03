"""Debate Subgraph 构建模块

本模块构建并编译 Debate Subgraph，实现 Author-Editor 对抗循环。

图结构：
    START → author → editor → increment_iteration → should_continue
        ├─ "author" → author  (继续下一轮)
        └─ "end" → finalize → END

循环终止条件：
- 评分达到 pass_score 阈值
- 迭代次数达到 max_iterations 上限
"""

from functools import lru_cache

from langgraph.graph import END, StateGraph

from app.core.logger import get_logger
from app.graph.polishing.debate import nodes as _nodes
from app.graph.polishing.debate.state import DebateState

logger = get_logger(__name__)


def _build_debate_graph() -> StateGraph:
    """构建 Debate Subgraph

    使用模块引用（_nodes.author_node）而非本地导入，
    以支持测试中通过 patch.object 替换节点函数。

    图结构：
        START → author → editor → increment_iteration -> should_continue
            ├─ "author" → author  (继续下一轮)
            └─ "end" → finalize -> END

    Returns:
        StateGraph: 编译前的图实例
    """
    graph = StateGraph(DebateState)

    # 添加节点（使用模块引用，便于测试 mock）
    graph.add_node("author", _nodes.author_node)
    graph.add_node("editor", _nodes.editor_node)
    graph.add_node("increment_iteration", _nodes.increment_iteration_node)
    graph.add_node("finalize", _nodes.finalize_debate_node)

    # 定义边
    graph.set_entry_point("author")
    graph.add_edge("author", "editor")
    graph.add_edge("editor", "increment_iteration")

    # 条件边：根据评分和迭代次数决定继续或结束
    graph.add_conditional_edges(
        "increment_iteration",
        _nodes.should_continue_debate,
        {
            "author": "author",
            "end": "finalize",
        },
    )

    graph.add_edge("finalize", END)

    return graph


@lru_cache(maxsize=1)
def get_debate_graph():
    """获取编译后的 Debate Subgraph 单例

    使用 lru_cache 确保全局只有一个编译后的图实例。

    Returns:
        CompiledStateGraph: 编译后的 Debate Subgraph
    """
    logger.info("编译 Debate Subgraph")
    graph = _build_debate_graph()
    return graph.compile()
