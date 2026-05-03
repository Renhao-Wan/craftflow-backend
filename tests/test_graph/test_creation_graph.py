"""Creation Graph 构建测试

测试 Creation Graph 的构建、节点配置和边定义。
使用 mock 隔离 LLM 调用，验证图结构和流转逻辑。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from app.graph.creation.builder import (
    build_creation_graph,
    get_creation_graph,
    _fan_out_writers,
    _route_after_planner,
    _route_after_writing,
    _route_after_reducer,
)
from app.graph.creation.state import CreationState


# ============================================
# 路由函数测试
# ============================================


class TestRouteFunctions:
    """测试路由函数"""

    def test_route_after_planner_success(self):
        """测试 PlannerNode 成功后的路由"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [{"title": "第一章", "summary": "概述"}],
            "sections": [],
            "final_draft": None,
            "messages": [],
            "current_node": "PlannerNode",
            "error": None,
        }
        assert _route_after_planner(state) == "outline_confirmation"

    def test_route_after_planner_error(self):
        """测试 PlannerNode 出错后的路由"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [],
            "sections": [],
            "final_draft": None,
            "messages": [],
            "current_node": "PlannerNode",
            "error": "生成大纲失败",
        }
        from langgraph.graph import END
        assert _route_after_planner(state) == END

    def test_route_after_writing_incomplete(self):
        """测试章节未完成时的路由"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [
                {"title": "第一章", "summary": "概述"},
                {"title": "第二章", "summary": "详情"},
            ],
            "sections": [
                {"title": "第一章", "content": "内容", "index": 0},
            ],
            "final_draft": None,
            "messages": [],
            "current_node": "WriterNode",
            "error": None,
        }
        assert _route_after_writing(state) == "fan_out"

    def test_route_after_writing_complete(self):
        """测试章节完成时的路由"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [
                {"title": "第一章", "summary": "概述"},
            ],
            "sections": [
                {"title": "第一章", "content": "内容", "index": 0},
            ],
            "final_draft": None,
            "messages": [],
            "current_node": "WriterNode",
            "error": None,
        }
        assert _route_after_writing(state) == "reducer"

    def test_route_after_writing_error(self):
        """测试 WriterNode 出错后的路由"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [],
            "sections": [],
            "final_draft": None,
            "messages": [],
            "current_node": "WriterNode",
            "error": "写作失败",
        }
        from langgraph.graph import END
        assert _route_after_writing(state) == END

    def test_route_after_reducer_success(self):
        """测试 ReducerNode 成功后的路由"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [],
            "sections": [],
            "final_draft": "# 完整文章",
            "messages": [],
            "current_node": "ReducerNode",
            "error": None,
        }
        from langgraph.graph import END
        assert _route_after_reducer(state) == END

    def test_route_after_reducer_error(self):
        """测试 ReducerNode 出错后的路由"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [],
            "sections": [],
            "final_draft": None,
            "messages": [],
            "current_node": "ReducerNode",
            "error": "合并失败",
        }
        from langgraph.graph import END
        assert _route_after_reducer(state) == END


# ============================================
# Fan Out 测试
# ============================================


class TestFanOutWriters:
    """测试扇出写作任务"""

    def test_fan_out_with_remaining_sections(self):
        """测试有待撰写章节时的扇出"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [
                {"title": "第一章", "summary": "概述"},
                {"title": "第二章", "summary": "详情"},
                {"title": "第三章", "summary": "总结"},
            ],
            "sections": [
                {"title": "第一章", "content": "内容", "index": 0},
            ],
            "final_draft": None,
            "messages": [],
            "current_node": "fan_out",
            "error": None,
        }

        sends = _fan_out_writers(state)

        # 应该扇出 2 个任务（第二章和第三章）
        assert len(sends) == 2

    def test_fan_out_all_complete(self):
        """测试所有章节已完成时的扇出"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [
                {"title": "第一章", "summary": "概述"},
            ],
            "sections": [
                {"title": "第一章", "content": "内容", "index": 0},
            ],
            "final_draft": None,
            "messages": [],
            "current_node": "fan_out",
            "error": None,
        }

        sends = _fan_out_writers(state)

        # 所有章节已完成，不应扇出
        assert len(sends) == 0

    def test_fan_out_empty_outline(self):
        """测试大纲为空时的扇出"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [],
            "sections": [],
            "final_draft": None,
            "messages": [],
            "current_node": "fan_out",
            "error": None,
        }

        sends = _fan_out_writers(state)

        # 大纲为空，不应扇出
        assert len(sends) == 0


# ============================================
# Graph 构建测试
# ============================================


class TestCreationGraph:
    """测试 Creation Graph 构建"""

    def test_build_creation_graph(self):
        """测试构建 Creation Graph"""
        graph = build_creation_graph()

        # 验证图已创建
        assert graph is not None

        # 验证节点存在
        nodes = list(graph.nodes)
        assert "planner" in nodes
        assert "outline_confirmation" in nodes
        assert "fan_out" in nodes
        assert "writer" in nodes
        assert "reducer" in nodes

    def test_creation_graph_compiled(self):
        """测试 Creation Graph 已编译"""
        graph = get_creation_graph()

        # 编译后的图应该有 invoke 方法
        assert hasattr(graph, "invoke")
        assert hasattr(graph, "ainvoke")
        assert hasattr(graph, "stream")
        assert hasattr(graph, "astream")


# ============================================
# 集成测试（Mock LLM）
# ============================================


class TestCreationGraphIntegration:
    """Creation Graph 集成测试"""

    @pytest.mark.asyncio
    async def test_graph_initial_state(self):
        """测试图的初始状态"""
        # Mock LLM
        mock_response = MagicMock()
        mock_response.content = '{"outline": [{"title": "引言", "summary": "介绍"}, {"title": "总结", "summary": "归纳"}]}'

        mock_llm_with_tools = AsyncMock()
        mock_llm_with_tools.ainvoke.return_value = mock_response

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm_with_tools

        with patch("app.graph.creation.nodes.get_default_llm", return_value=mock_llm):
            graph = get_creation_graph()

            # 初始状态
            initial_state: CreationState = {
                "topic": "人工智能",
                "description": "讨论 AI 发展趋势",
                "outline": [],
                "sections": [],
                "final_draft": None,
                "messages": [],
                "current_node": None,
                "error": None,
            }

            # 执行图（应该在 outline_confirmation 中断）
            config = {"configurable": {"thread_id": "test-thread-1"}}
            result = await graph.ainvoke(initial_state, config)

            # 验证大纲已生成
            assert "outline" in result
            assert len(result["outline"]) > 0
            # interrupt_before 会在到达 outline_confirmation 之前暂停
            # 返回的状态是 PlannerNode 执行后的状态
            assert result["current_node"] == "PlannerNode"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
