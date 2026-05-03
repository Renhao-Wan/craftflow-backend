"""Polishing Graph 节点单元测试

测试 router_node、formatter_node、fact_checker_node、author_node、editor_node 的核心逻辑。
使用 mock 隔离 LLM 调用，验证节点的状态更新行为。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from app.graph.polishing.nodes import (
    _extract_json_from_response,
    author_node,
    editor_node,
    fact_checker_node,
    formatter_node,
    route_by_mode,
    router_node,
    should_continue_debate,
)
from app.graph.polishing.state import DebateState, PolishingState


# ============================================
# 辅助函数测试
# ============================================


class TestExtractJsonFromResponse:
    """测试 JSON 提取函数"""

    def test_extract_json_direct(self):
        """测试直接解析 JSON"""
        text = '{"recommended_mode": 2, "reason": "测试"}'
        result = _extract_json_from_response(text)
        assert result is not None
        assert result["recommended_mode"] == 2

    def test_extract_json_from_code_block(self):
        """测试从代码块中提取 JSON"""
        text = """分析结果：
```json
{
  "recommended_mode": 1,
  "reason": "格式问题"
}
```"""
        result = _extract_json_from_response(text)
        assert result is not None
        assert result["recommended_mode"] == 1

    def test_extract_json_failure(self):
        """测试解析失败的情况"""
        text = "这不是 JSON 格式的内容"
        result = _extract_json_from_response(text)
        assert result is None


# ============================================
# 条件边函数测试
# ============================================


class TestConditionalEdges:
    """测试条件边函数"""

    def test_route_by_mode_1(self):
        """测试模式 1 路由到 formatter"""
        state: PolishingState = {
            "content": "测试内容",
            "mode": 1,
            "current_node": "router",
            "error": None,
            "formatted_content": None,
            "fact_check_result": None,
            "debate_history": [],
            "final_content": None,
            "scores": [],
            "overall_score": None,
            "messages": [],
        }
        assert route_by_mode(state) == "formatter"

    def test_route_by_mode_2(self):
        """测试模式 2 路由到 author"""
        state: PolishingState = {
            "content": "测试内容",
            "mode": 2,
            "current_node": "router",
            "error": None,
            "formatted_content": None,
            "fact_check_result": None,
            "debate_history": [],
            "final_content": None,
            "scores": [],
            "overall_score": None,
            "messages": [],
        }
        assert route_by_mode(state) == "author"

    def test_route_by_mode_3(self):
        """测试模式 3 路由到 fact_checker"""
        state: PolishingState = {
            "content": "测试内容",
            "mode": 3,
            "current_node": "router",
            "error": None,
            "formatted_content": None,
            "fact_check_result": None,
            "debate_history": [],
            "final_content": None,
            "scores": [],
            "overall_score": None,
            "messages": [],
        }
        assert route_by_mode(state) == "fact_checker"

    def test_should_continue_debate_passed(self):
        """测试评分达标时结束"""
        state: DebateState = {
            "content": "测试内容",
            "topic": None,
            "current_iteration": 1,
            "max_iterations": 3,
            "pass_score": 90,
            "author_output": "润色内容",
            "editor_feedback": "优秀",
            "editor_score": 95,
            "debate_history": [],
            "final_content": None,
            "is_passed": True,
            "messages": [],
            "error": None,
        }
        assert should_continue_debate(state) == "end"

    def test_should_continue_debate_max_iterations(self):
        """测试达到最大迭代次数时结束"""
        state: DebateState = {
            "content": "测试内容",
            "topic": None,
            "current_iteration": 3,
            "max_iterations": 3,
            "pass_score": 90,
            "author_output": "润色内容",
            "editor_feedback": "需要改进",
            "editor_score": 85,
            "debate_history": [],
            "final_content": None,
            "is_passed": False,
            "messages": [],
            "error": None,
        }
        assert should_continue_debate(state) == "end"

    def test_should_continue_debate_continue(self):
        """测试继续对抗循环"""
        state: DebateState = {
            "content": "测试内容",
            "topic": None,
            "current_iteration": 1,
            "max_iterations": 3,
            "pass_score": 90,
            "author_output": "润色内容",
            "editor_feedback": "需要改进",
            "editor_score": 80,
            "debate_history": [],
            "final_content": None,
            "is_passed": False,
            "messages": [],
            "error": None,
        }
        assert should_continue_debate(state) == "author"


# ============================================
# 节点函数测试（Mock LLM）
# ============================================


class TestRouterNode:
    """测试 RouterNode"""

    @pytest.mark.asyncio
    async def test_router_with_user_mode(self):
        """测试用户指定模式时直接使用"""
        state: PolishingState = {
            "content": "测试内容",
            "mode": 1,
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

        result = await router_node(state)

        assert result["mode"] == 1
        assert result["current_node"] == "router"

    @pytest.mark.asyncio
    async def test_router_with_llm_recommendation(self):
        """测试 LLM 推荐模式"""
        mock_response = MagicMock()
        mock_response.content = '{"recommended_mode": 2, "reason": "需要深度润色"}'

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response

        with patch("app.graph.polishing.nodes.get_default_llm", return_value=mock_llm):
            state: PolishingState = {
                "content": "测试内容",
                "mode": 2,  # 默认值
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

            result = await router_node(state)

            assert result["current_node"] == "router"


class TestFormatterNode:
    """测试 FormatterNode"""

    @pytest.mark.asyncio
    async def test_formatter_success(self):
        """测试成功格式化"""
        mock_response = MagicMock()
        mock_response.content = "# 格式化后的内容\n\n正文..."

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response

        with patch("app.graph.polishing.nodes.get_default_llm", return_value=mock_llm):
            state: PolishingState = {
                "content": "原始内容",
                "mode": 1,
                "current_node": "router",
                "error": None,
                "formatted_content": None,
                "fact_check_result": None,
                "debate_history": [],
                "final_content": None,
                "scores": [],
                "overall_score": None,
                "messages": [],
            }

            result = await formatter_node(state)

            assert "formatted_content" in result
            assert "final_content" in result
            assert result["current_node"] == "formatter"


class TestFactCheckerNode:
    """测试 FactCheckerNode"""

    @pytest.mark.asyncio
    async def test_fact_checker_success(self):
        """测试成功事实核查"""
        mock_response = MagicMock()
        mock_response.content = '{"overall_accuracy": "high", "issues": [], "summary": "内容准确"}'

        mock_llm_with_tools = AsyncMock()
        mock_llm_with_tools.ainvoke.return_value = mock_response

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm_with_tools

        with patch("app.graph.polishing.nodes.get_default_llm", return_value=mock_llm):
            state: PolishingState = {
                "content": "测试内容",
                "mode": 3,
                "current_node": "router",
                "error": None,
                "formatted_content": None,
                "fact_check_result": None,
                "debate_history": [],
                "final_content": None,
                "scores": [],
                "overall_score": None,
                "messages": [],
            }

            result = await fact_checker_node(state)

            assert "fact_check_result" in result
            assert result["current_node"] == "fact_checker"


class TestAuthorNode:
    """测试 AuthorNode"""

    @pytest.mark.asyncio
    async def test_author_success(self):
        """测试成功重写"""
        mock_response = MagicMock()
        mock_response.content = "# 润色后的文章\n\n优化后的内容..."

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response

        with patch("app.graph.polishing.nodes.get_default_llm", return_value=mock_llm):
            state: DebateState = {
                "content": "原始内容",
                "topic": None,
                "current_iteration": 1,
                "max_iterations": 3,
                "pass_score": 90,
                "author_output": None,
                "editor_feedback": "需要改进",
                "editor_score": 80,
                "debate_history": [],
                "final_content": None,
                "is_passed": False,
                "messages": [],
                "error": None,
            }

            result = await author_node(state)

            assert "author_output" in result
            assert "润色后" in result["author_output"]


class TestEditorNode:
    """测试 EditorNode"""

    @pytest.mark.asyncio
    async def test_editor_success(self):
        """测试成功评估"""
        mock_response = MagicMock()
        mock_response.content = '''{
            "scores": [
                {"dimension": "逻辑性", "score": 22, "comment": "逻辑清晰"},
                {"dimension": "可读性", "score": 20, "comment": "语言流畅"},
                {"dimension": "准确性", "score": 23, "comment": "事实准确"},
                {"dimension": "专业性", "score": 21, "comment": "内容深入"}
            ],
            "total_score": 86,
            "feedback": "整体质量良好",
            "highlights": ["论证充分"],
            "improvements": ["段落可更精炼"]
        }'''

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = mock_response

        with patch("app.graph.polishing.nodes.get_editor_llm", return_value=mock_llm):
            state: DebateState = {
                "content": "测试内容",
                "topic": None,
                "current_iteration": 1,
                "max_iterations": 3,
                "pass_score": 90,
                "author_output": "润色内容",
                "editor_feedback": None,
                "editor_score": 0,
                "debate_history": [],
                "final_content": None,
                "is_passed": False,
                "messages": [],
                "error": None,
            }

            result = await editor_node(state)

            assert result["editor_score"] == 86
            assert result["is_passed"] is False  # 86 < 90
            assert len(result["debate_history"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
