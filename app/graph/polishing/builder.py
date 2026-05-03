"""Polishing Graph 构建模块

本模块构建并编译 Polishing 主图，支持三档润色模式：
- Mode 1: 极速格式化（formatter）
- Mode 2: 专家对抗审查（Debate Subgraph）
- Mode 3: 事实核查（fact_checker）

图结构：
    START → router → route_by_mode
        ├─ "formatter" → formatter → END
        ├─ "debate" → debate_node → END
        └─ "fact_checker" → fact_checker → END

Debate Subgraph 作为独立节点嵌入主图，通过 debate_node 包装
实现 PolishingState ↔ DebateState 的状态映射，保持两层状态定义分离。
"""

from functools import lru_cache

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from app.core.logger import get_logger
from app.graph.polishing import nodes as _nodes
from app.graph.polishing.debate.builder import get_debate_graph
from app.graph.polishing.debate.state import DebateState
from app.graph.polishing.state import PolishingState

logger = get_logger(__name__)

# Debate 默认参数
DEFAULT_MAX_ITERATIONS = 3
DEFAULT_PASS_SCORE = 90


# ============================================
# Debate 包装节点
# ============================================


async def debate_node(state: PolishingState) -> dict:
    """Debate 包装节点：调用 Debate Subgraph 并映射状态

    将 PolishingState 映射为 DebateState，调用编译后的
    Debate Subgraph，再将结果映射回 PolishingState 增量更新。

    Args:
        state: 主图状态（PolishingState）

    Returns:
        dict: 主图状态增量更新
    """
    content = state.get("content", "")
    messages_before = len(state.get("messages", []))

    # 构建 DebateState 输入
    debate_input: DebateState = {
        "content": content,
        "topic": None,
        "current_iteration": 0,
        "max_iterations": DEFAULT_MAX_ITERATIONS,
        "pass_score": DEFAULT_PASS_SCORE,
        "author_output": None,
        "editor_feedback": None,
        "editor_score": 0,
        "debate_history": [],
        "final_content": None,
        "is_passed": False,
        "messages": [],
        "error": None,
    }

    logger.info(
        f"Debate 子图启动 - 最大迭代: {DEFAULT_MAX_ITERATIONS}, "
        f"通过分数: {DEFAULT_PASS_SCORE}"
    )

    try:
        # 调用编译后的 Debate Subgraph
        debate_graph = get_debate_graph()
        result = await debate_graph.ainvoke(debate_input)

        # 提取子图新增的消息（避免与主图 messages reducer 重复累加）
        all_messages = result.get("messages", [])
        new_messages = all_messages[messages_before:]

        logger.info(
            f"Debate 子图完成 - 最终评分: {result.get('editor_score', 0)}, "
            f"通过: {result.get('is_passed', False)}"
        )

        # 映射回 PolishingState 增量更新
        return {
            "final_content": result.get("final_content"),
            "debate_history": result.get("debate_history", []),
            "overall_score": result.get("editor_score"),
            "current_node": "debate",
            "messages": new_messages if new_messages else [
                AIMessage(content="对抗审查完成")
            ],
        }

    except Exception as e:
        logger.error(f"Debate 子图执行失败: {str(e)}")
        return {
            "error": f"对抗审查失败: {str(e)}",
            "current_node": "debate",
            "messages": [AIMessage(content=f"对抗审查失败: {str(e)}")],
        }


# ============================================
# 图构建
# ============================================


def _build_polishing_graph() -> StateGraph:
    """构建 Polishing 主图

    图结构：
        START → router → route_by_mode
            ├─ "formatter" → formatter → END
            ├─ "debate" → debate_node → END
            └─ "fact_checker" → fact_checker → END

    Returns:
        StateGraph: 编译前的图实例
    """
    graph = StateGraph(PolishingState)

    # ---- 添加节点 ----

    graph.add_node("router", _nodes.router_node)
    graph.add_node("formatter", _nodes.formatter_node)
    graph.add_node("debate", debate_node)
    graph.add_node("fact_checker", _nodes.fact_checker_node)

    # ---- 定义边 ----

    # 入口
    graph.set_entry_point("router")

    # 路由分发
    graph.add_conditional_edges(
        "router",
        _nodes.route_by_mode,
        {
            "formatter": "formatter",
            "author": "debate",
            "fact_checker": "fact_checker",
        },
    )

    # 各模式 → END
    graph.add_edge("formatter", END)
    graph.add_edge("debate", END)
    graph.add_edge("fact_checker", END)

    return graph


@lru_cache(maxsize=1)
def get_polishing_graph():
    """获取编译后的 Polishing Graph 单例

    使用 lru_cache 确保全局只有一个编译后的图实例。

    Returns:
        CompiledStateGraph: 编译后的 Polishing Graph
    """
    logger.info("编译 Polishing Graph")
    graph = _build_polishing_graph()
    return graph.compile()
