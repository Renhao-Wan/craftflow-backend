"""Debate Subgraph 单元测试

测试 increment_iteration_node、finalize_debate_node、get_debate_graph 的核心逻辑。
使用 mock 隔离 LLM 调用，验证子图的结构和状态流转行为。
"""

import pytest
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from app.graph.polishing.debate import nodes as _debate_nodes_module
from app.graph.polishing.debate.builder import _build_debate_graph, get_debate_graph
from app.graph.polishing.debate.nodes import (
    finalize_debate_node,
    increment_iteration_node,
)
from app.graph.polishing.debate.state import DebateState


# ============================================
# 辅助函数
# ============================================


def _make_debate_state(**overrides) -> DebateState:
    """构建默认的 DebateState，支持字段覆盖"""
    base: DebateState = {
        "content": "原始内容",
        "topic": None,
        "current_iteration": 1,
        "max_iterations": 3,
        "pass_score": 90,
        "author_output": "润色后的内容",
        "editor_feedback": "需要改进",
        "editor_score": 80,
        "debate_history": [],
        "final_content": None,
        "is_passed": False,
        "messages": [],
        "error": None,
    }
    base.update(overrides)
    return base


# ============================================
# increment_iteration_node 测试
# ============================================


class TestIncrementIterationNode:
    """测试迭代计数递增节点"""

    @pytest.mark.asyncio
    async def test_increment_from_zero(self):
        """测试从 0 递增到 1"""
        state = _make_debate_state(current_iteration=0)

        result = await increment_iteration_node(state)

        assert result["current_iteration"] == 1

    @pytest.mark.asyncio
    async def test_increment_from_one(self):
        """测试从 1 递增到 2"""
        state = _make_debate_state(current_iteration=1)

        result = await increment_iteration_node(state)

        assert result["current_iteration"] == 2

    @pytest.mark.asyncio
    async def test_increment_from_two(self):
        """测试从 2 递增到 3"""
        state = _make_debate_state(current_iteration=2)

        result = await increment_iteration_node(state)

        assert result["current_iteration"] == 3

    @pytest.mark.asyncio
    async def test_increment_emits_message(self):
        """测试递增时生成消息"""
        state = _make_debate_state(current_iteration=1)

        result = await increment_iteration_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1
        assert "2" in result["messages"][0].content


# ============================================
# finalize_debate_node 测试
# ============================================


class TestFinalizeDebateNode:
    """测试终结节点"""

    @pytest.mark.asyncio
    async def test_finalize_with_author_output(self):
        """测试使用 author_output 作为 final_content"""
        state = _make_debate_state(
            author_output="最终润色内容",
            is_passed=True,
            editor_score=95,
            current_iteration=2,
        )

        result = await finalize_debate_node(state)

        assert result["final_content"] == "最终润色内容"

    @pytest.mark.asyncio
    async def test_finalize_fallback_to_content(self):
        """测试 author_output 为空时回退到 content"""
        state = _make_debate_state(
            author_output=None,
            content="原始内容",
        )

        result = await finalize_debate_node(state)

        assert result["final_content"] == "原始内容"

    @pytest.mark.asyncio
    async def test_finalize_empty_author_output(self):
        """测试 author_output 为空字符串时回退"""
        state = _make_debate_state(
            author_output="",
            content="原始内容",
        )

        result = await finalize_debate_node(state)

        assert result["final_content"] == "原始内容"

    @pytest.mark.asyncio
    async def test_finalize_message_contains_score(self):
        """测试消息包含最终评分"""
        state = _make_debate_state(editor_score=88, current_iteration=3)

        result = await finalize_debate_node(state)

        message = result["messages"][0].content
        assert "88" in message
        assert "3" in message

    @pytest.mark.asyncio
    async def test_finalize_message_contains_pass_status(self):
        """测试消息包含通过状态"""
        state = _make_debate_state(is_passed=True)

        result = await finalize_debate_node(state)

        assert "True" in result["messages"][0].content


# ============================================
# get_debate_graph 测试
# ============================================


class TestGetDebateGraph:
    """测试 Debate Subgraph 编译与结构"""

    def test_returns_compiled_graph(self):
        """测试返回编译后的图实例"""
        graph = get_debate_graph()

        assert graph is not None
        # 编译后的图应有 ainvoke 方法
        assert hasattr(graph, "ainvoke")

    def test_graph_is_singleton(self):
        """测试图是单例"""
        graph1 = get_debate_graph()
        graph2 = get_debate_graph()

        assert graph1 is graph2

    def test_graph_has_required_nodes(self):
        """测试图包含必要的节点"""
        graph = get_debate_graph()

        # 编译后的图可通过 get_graph() 获取结构
        graph_repr = graph.get_graph()
        node_ids = list(graph_repr.nodes.keys())

        assert "author" in node_ids
        assert "editor" in node_ids
        assert "increment_iteration" in node_ids
        assert "finalize" in node_ids

    def test_graph_has_entry_and_exit(self):
        """测试图有入口和出口"""
        graph = get_debate_graph()

        graph_repr = graph.get_graph()
        node_ids = list(graph_repr.nodes.keys())

        # LangGraph 添加 __start__ 和 __end__ 节点
        assert "__start__" in node_ids
        assert "__end__" in node_ids


# ============================================
# 端到端测试（Mock LLM）
# ============================================


def _build_initial_state() -> DebateState:
    """构建标准的初始 DebateState"""
    return {
        "content": "测试文章",
        "topic": None,
        "current_iteration": 0,
        "max_iterations": 3,
        "pass_score": 90,
        "author_output": None,
        "editor_feedback": None,
        "editor_score": 0,
        "debate_history": [],
        "final_content": None,
        "is_passed": False,
        "messages": [],
        "error": None,
    }


def _rebuild_graph_with_mocks(author_mock, editor_mock):
    """清除缓存并使用 mock 节点重新构建图"""
    get_debate_graph.cache_clear()
    with (
        patch.object(_debate_nodes_module, "author_node", author_mock),
        patch.object(_debate_nodes_module, "editor_node", editor_mock),
    ):
        # 直接调用 _build_debate_graph() 绕过 lru_cache，
        # 因为 from ... import 在模块加载时已绑定函数引用
        return _build_debate_graph().compile()


class TestDebateGraphE2E:
    """测试 Debate Subgraph 端到端流程"""

    @pytest.mark.asyncio
    async def test_debate_passes_on_high_score(self):
        """测试高分通过时循环结束"""
        mock_author = AsyncMock(return_value={
            "author_output": "高质量润色内容",
            "messages": [AIMessage(content="重写完成")],
        })
        mock_editor = AsyncMock(return_value={
            "editor_feedback": "优秀",
            "editor_score": 95,
            "debate_history": [],
            "is_passed": True,
            "messages": [AIMessage(content="评分 95/100")],
        })

        graph = _rebuild_graph_with_mocks(mock_author, mock_editor)
        result = await graph.ainvoke(_build_initial_state())

        # 应该在第一轮就通过
        assert result["final_content"] == "高质量润色内容"
        assert result["is_passed"] is True
        assert result["current_iteration"] == 1

    @pytest.mark.asyncio
    async def test_debate_loops_until_max_iterations(self):
        """测试达到最大迭代次数时循环结束"""
        call_count = {"author": 0, "editor": 0}

        async def mock_author(state):
            call_count["author"] += 1
            return {
                "author_output": f"第 {call_count['author']} 轮润色",
                "messages": [AIMessage(content="重写完成")],
            }

        async def mock_editor(state):
            call_count["editor"] += 1
            return {
                "editor_feedback": "需要改进",
                "editor_score": 80,  # 低于 pass_score=90
                "debate_history": [],
                "is_passed": False,
                "messages": [AIMessage(content="评分 80/100")],
            }

        graph = _rebuild_graph_with_mocks(mock_author, mock_editor)
        result = await graph.ainvoke(_build_initial_state())

        # 应该执行 3 轮后结束
        assert call_count["author"] == 3
        assert call_count["editor"] == 3
        assert result["current_iteration"] == 3
        assert result["final_content"] is not None

    @pytest.mark.asyncio
    async def test_debate_passes_on_second_round(self):
        """测试第二轮评分达标时结束"""
        call_count = {"author": 0, "editor": 0}

        async def mock_author(state):
            call_count["author"] += 1
            return {
                "author_output": f"第 {call_count['author']} 轮润色",
                "messages": [AIMessage(content="重写完成")],
            }

        async def mock_editor(state):
            call_count["editor"] += 1
            score = 95 if call_count["editor"] >= 2 else 75
            return {
                "editor_feedback": "优秀" if score >= 90 else "需要改进",
                "editor_score": score,
                "debate_history": [],
                "is_passed": score >= 90,
                "messages": [AIMessage(content=f"评分 {score}/100")],
            }

        graph = _rebuild_graph_with_mocks(mock_author, mock_editor)
        result = await graph.ainvoke(_build_initial_state())

        # 应该在第二轮通过
        assert call_count["author"] == 2
        assert result["is_passed"] is True
        assert result["current_iteration"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
