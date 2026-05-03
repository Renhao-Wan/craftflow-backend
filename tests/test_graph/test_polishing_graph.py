"""Polishing Graph 构建测试

测试 get_polishing_graph 的图结构、单例行为和三档模式的端到端流程。
使用 mock 隔离 LLM 调用和子图调用，验证图的状态流转。
"""

import pytest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from app.graph.polishing import builder as _builder_module
from app.graph.polishing import nodes as _nodes_module
from app.graph.polishing.builder import get_polishing_graph
from app.graph.polishing.state import PolishingState


# ============================================
# 辅助函数
# ============================================


def _make_polishing_state(mode: int = 2, **overrides) -> PolishingState:
    """构建默认的 PolishingState，支持字段覆盖"""
    base: PolishingState = {
        "content": "测试文章内容",
        "mode": mode,
        "current_node": None,
        "error": None,
        "formatted_content": None,
        "fact_check_result": None,
        "debate_history": [],
        "final_content": None,
        "scores": [],
        "overall_score": None,
        "messages": [],
    }
    base.update(overrides)
    return base


def _rebuild_graph(**node_mocks):
    """使用 mock 节点重新构建图

    builder.py 使用模块引用（_nodes.router_node 等），
    所以只需 patch nodes 模块即可。debate_node 定义在 builder.py 中。

    Args:
        **node_mocks: 节点名 -> mock 函数的映射
            支持的键: router_node, formatter_node, fact_checker_node (nodes.py)
                      debate_node (builder.py)
    """
    _builder_only = {"debate_node"}

    patches = []
    for node_name, mock_fn in node_mocks.items():
        if node_name in _builder_only:
            patches.append(patch.object(_builder_module, node_name, mock_fn))
        else:
            # builder 使用 _nodes.router_node，patch nodes 模块即可
            patches.append(patch.object(_nodes_module, node_name, mock_fn))

    for p in patches:
        p.__enter__()

    try:
        graph = get_polishing_graph()
    finally:
        for p in reversed(patches):
            p.__exit__(None, None, None)

    return graph


def _make_debate_result(
    final_content: str = "润色后的内容",
    editor_score: float = 95,
    is_passed: bool = True,
    debate_history: list | None = None,
    messages: list | None = None,
) -> dict:
    """构建 Debate Subgraph 的模拟返回结果"""
    return {
        "content": "测试文章内容",
        "topic": None,
        "current_iteration": 1,
        "max_iterations": 3,
        "pass_score": 90,
        "author_output": final_content,
        "editor_feedback": "优秀",
        "editor_score": editor_score,
        "debate_history": debate_history or [],
        "final_content": final_content,
        "is_passed": is_passed,
        "messages": messages or [AIMessage(content="对抗审查完成")],
        "error": None,
    }


# ============================================
# 图结构测试
# ============================================


class TestPolishingGraphStructure:
    """测试 Polishing Graph 的编译与结构"""

    def test_returns_compiled_graph(self):
        """测试返回编译后的图实例"""
        graph = get_polishing_graph()

        assert graph is not None
        assert hasattr(graph, "ainvoke")

    def test_graph_has_required_nodes(self):
        """测试图包含所有必要节点"""
        graph = get_polishing_graph()

        graph_repr = graph.get_graph()
        node_ids = list(graph_repr.nodes.keys())

        # 路由节点
        assert "router" in node_ids
        # Mode 1
        assert "formatter" in node_ids
        # Mode 2: Debate Subgraph 包装节点
        assert "debate" in node_ids
        # Mode 3
        assert "fact_checker" in node_ids

    def test_graph_has_entry_and_exit(self):
        """测试图有入口和出口"""
        graph = get_polishing_graph()

        graph_repr = graph.get_graph()
        node_ids = list(graph_repr.nodes.keys())

        assert "__start__" in node_ids
        assert "__end__" in node_ids


# ============================================
# Mode 1 端到端测试
# ============================================


class TestPolishingMode1:
    """测试 Mode 1: 极速格式化"""

    @pytest.mark.asyncio
    async def test_mode1_formatter(self):
        """测试 Mode 1 路由到 formatter 并返回格式化内容"""
        mock_router = AsyncMock(return_value={
            "mode": 1,
            "current_node": "router",
            "messages": [AIMessage(content="已选择润色模式: 1")],
        })
        mock_formatter = AsyncMock(return_value={
            "formatted_content": "# 格式化后的内容\n\n正文...",
            "final_content": "# 格式化后的内容\n\n正文...",
            "current_node": "formatter",
            "messages": [AIMessage(content="文章格式化完成")],
        })

        graph = _rebuild_graph(
            router_node=mock_router,
            formatter_node=mock_formatter,
        )

        state = _make_polishing_state(mode=1)
        result = await graph.ainvoke(state)

        assert result["final_content"] == "# 格式化后的内容\n\n正文..."
        assert result["formatted_content"] == "# 格式化后的内容\n\n正文..."
        mock_formatter.assert_called_once()


# ============================================
# Mode 2 端到端测试
# ============================================


class TestPolishingMode2:
    """测试 Mode 2: 专家对抗审查（Debate Subgraph）"""

    @pytest.mark.asyncio
    async def test_mode2_debate_pass(self):
        """测试 Mode 2 对抗审查通过"""
        mock_router = AsyncMock(return_value={
            "mode": 2,
            "current_node": "router",
            "messages": [AIMessage(content="已选择润色模式: 2")],
        })

        debate_result = _make_debate_result(
            final_content="高质量润色内容",
            editor_score=95,
            is_passed=True,
        )
        mock_debate = AsyncMock(return_value={
            "final_content": debate_result["final_content"],
            "debate_history": debate_result["debate_history"],
            "overall_score": debate_result["editor_score"],
            "current_node": "debate",
            "messages": [AIMessage(content="对抗审查完成")],
        })

        graph = _rebuild_graph(
            router_node=mock_router,
            debate_node=mock_debate,
        )

        state = _make_polishing_state(mode=2)
        result = await graph.ainvoke(state)

        assert result["final_content"] == "高质量润色内容"
        assert result["overall_score"] == 95
        mock_debate.assert_called_once()

    @pytest.mark.asyncio
    async def test_mode2_debate_with_history(self):
        """测试 Mode 2 返回对抗历史"""
        mock_router = AsyncMock(return_value={
            "mode": 2,
            "current_node": "router",
            "messages": [AIMessage(content="已选择润色模式: 2")],
        })

        history = [
            {"round_number": 1, "author_content": "第一轮", "editor_feedback": "改进", "editor_score": 75},
            {"round_number": 2, "author_content": "第二轮", "editor_feedback": "优秀", "editor_score": 95},
        ]
        mock_debate = AsyncMock(return_value={
            "final_content": "最终润色内容",
            "debate_history": history,
            "overall_score": 95,
            "current_node": "debate",
            "messages": [AIMessage(content="对抗审查完成")],
        })

        graph = _rebuild_graph(
            router_node=mock_router,
            debate_node=mock_debate,
        )

        state = _make_polishing_state(mode=2)
        result = await graph.ainvoke(state)

        assert len(result["debate_history"]) == 2
        assert result["debate_history"][1]["editor_score"] == 95

    @pytest.mark.asyncio
    async def test_mode2_debate_error(self):
        """测试 Mode 2 对抗审查失败时的错误处理"""
        mock_router = AsyncMock(return_value={
            "mode": 2,
            "current_node": "router",
            "messages": [AIMessage(content="已选择润色模式: 2")],
        })
        mock_debate = AsyncMock(return_value={
            "error": "对抗审查失败: LLM 调用超时",
            "current_node": "debate",
            "messages": [AIMessage(content="对抗审查失败: LLM 调用超时")],
        })

        graph = _rebuild_graph(
            router_node=mock_router,
            debate_node=mock_debate,
        )

        state = _make_polishing_state(mode=2)
        result = await graph.ainvoke(state)

        assert result["error"] is not None
        assert "失败" in result["error"]


# ============================================
# Mode 3 端到端测试
# ============================================


class TestPolishingMode3:
    """测试 Mode 3: 事实核查"""

    @pytest.mark.asyncio
    async def test_mode3_fact_checker(self):
        """测试 Mode 3 路由到 fact_checker 并返回核查结果"""
        mock_router = AsyncMock(return_value={
            "mode": 3,
            "current_node": "router",
            "messages": [AIMessage(content="已选择润色模式: 3")],
        })
        mock_fact_checker = AsyncMock(return_value={
            "fact_check_result": "事实核查完成，准确性: high",
            "current_node": "fact_checker",
            "messages": [AIMessage(content="事实核查完成")],
        })

        graph = _rebuild_graph(
            router_node=mock_router,
            fact_checker_node=mock_fact_checker,
        )

        state = _make_polishing_state(mode=3)
        result = await graph.ainvoke(state)

        assert result["fact_check_result"] is not None
        assert "high" in result["fact_check_result"]
        mock_fact_checker.assert_called_once()


# ============================================
# 集成测试
# ============================================


class TestPolishingGraphIntegration:
    """测试 Polishing Graph 的集成功能"""

    def test_graph_node_count(self):
        """测试图节点数量"""
        graph = get_polishing_graph()

        graph_repr = graph.get_graph()
        node_ids = list(graph_repr.nodes.keys())

        # 4 个业务节点（router, formatter, debate, fact_checker）+ __start__ + __end__
        assert len(node_ids) == 6

    def test_graph_edges_include_conditional(self):
        """测试图包含条件边"""
        graph = get_polishing_graph()

        graph_repr = graph.get_graph()
        edges = list(graph_repr.edges)

        # 应该有多条边（包括条件边）
        assert len(edges) >= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
