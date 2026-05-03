"""Creation Graph 节点单元测试

测试 planner_node、writer_node、reducer_node 的核心逻辑。
使用 mock 隔离 LLM 调用，验证节点的状态更新行为。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage

from app.graph.creation.nodes import (
    _extract_json_from_response,
    planner_node,
    reducer_node,
    writer_node,
)
from app.graph.creation.state import CreationState


# ============================================
# 辅助函数测试
# ============================================


class TestExtractJsonFromResponse:
    """测试 JSON 提取函数"""

    def test_extract_json_direct(self):
        """测试直接解析 JSON"""
        text = '{"outline": [{"title": "测试", "summary": "摘要"}]}'
        result = _extract_json_from_response(text)
        assert result is not None
        assert "outline" in result
        assert len(result["outline"]) == 1

    def test_extract_json_from_code_block(self):
        """测试从代码块中提取 JSON"""
        text = """这是大纲：
```json
{
  "outline": [
    {"title": "第一章", "summary": "概述"}
  ]
}
```"""
        result = _extract_json_from_response(text)
        assert result is not None
        assert "outline" in result

    def test_extract_json_from_object(self):
        """测试从混合文本中提取 JSON 对象"""
        text = '根据主题，我生成了以下大纲：{"outline": [{"title": "引言", "summary": "介绍"}]}'
        result = _extract_json_from_response(text)
        assert result is not None
        assert "outline" in result

    def test_extract_json_failure(self):
        """测试解析失败的情况"""
        text = "这不是 JSON 格式的内容"
        result = _extract_json_from_response(text)
        assert result is None


# ============================================
# 节点函数测试（Mock LLM）
# ============================================


class TestPlannerNode:
    """测试 PlannerNode"""

    @pytest.mark.asyncio
    async def test_planner_node_success(self):
        """测试成功生成大纲"""
        mock_response = MagicMock()
        mock_response.content = '{"outline": [{"title": "引言", "summary": "介绍主题"}, {"title": "总结", "summary": "归纳观点"}]}'

        mock_llm_with_tools = AsyncMock()
        mock_llm_with_tools.ainvoke.return_value = mock_response

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm_with_tools

        with patch("app.graph.creation.nodes.get_default_llm", return_value=mock_llm):
            state: CreationState = {
                "topic": "人工智能",
                "description": "讨论 AI 的发展趋势",
                "outline": [],
                "sections": [],
                "final_draft": None,
                "messages": [],
                "current_node": None,
                "error": None,
            }

            result = await planner_node(state)

            assert "outline" in result
            assert len(result["outline"]) == 2
            assert result["outline"][0]["title"] == "引言"
            assert "messages" in result
            assert len(result["messages"]) > 0

    @pytest.mark.asyncio
    async def test_planner_node_json_parse_failure(self):
        """测试 JSON 解析失败时使用默认大纲"""
        mock_response = MagicMock()
        mock_response.content = "这是一个大纲，但不是 JSON 格式"

        mock_llm_with_tools = AsyncMock()
        mock_llm_with_tools.ainvoke.return_value = mock_response

        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm_with_tools

        with patch("app.graph.creation.nodes.get_default_llm", return_value=mock_llm):
            state: CreationState = {
                "topic": "测试主题",
                "description": None,
                "outline": [],
                "sections": [],
                "final_draft": None,
                "messages": [],
                "current_node": None,
                "error": None,
            }

            result = await planner_node(state)

            assert "outline" in result
            assert len(result["outline"]) == 4  # 默认大纲有 4 个章节


class TestWriterNode:
    """测试 WriterNode"""

    @pytest.mark.asyncio
    async def test_writer_node_success(self):
        """测试成功撰写章节"""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content="## 第一章内容\n\n这是第一章的详细内容..."
        )

        with patch("app.graph.creation.nodes.get_default_llm", return_value=mock_llm):
            state: CreationState = {
                "topic": "人工智能",
                "description": None,
                "outline": [
                    {"title": "引言", "summary": "介绍主题"},
                    {"title": "总结", "summary": "归纳观点"},
                ],
                "sections": [],
                "final_draft": None,
                "messages": [],
                "current_node": "PlannerNode",
                "error": None,
            }

            result = await writer_node(state)

            assert "sections" in result
            assert len(result["sections"]) == 1
            assert result["sections"][0]["title"] == "引言"
            assert result["sections"][0]["index"] == 0

    @pytest.mark.asyncio
    async def test_writer_node_all_sections_complete(self):
        """测试所有章节已完成时的行为"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [{"title": "引言", "summary": "概述"}],
            "sections": [{"title": "引言", "content": "内容", "index": 0}],
            "final_draft": None,
            "messages": [],
            "current_node": "WriterNode",
            "error": None,
        }

        result = await writer_node(state)

        # 所有章节已完成，不应生成新的 section
        assert "sections" not in result or len(result.get("sections", [])) == 0


class TestReducerNode:
    """测试 ReducerNode"""

    @pytest.mark.asyncio
    async def test_reducer_node_success(self):
        """测试成功合并章节"""
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = MagicMock(
            content="# 人工智能\n\n## 引言\n\n介绍内容...\n\n## 总结\n\n归纳内容..."
        )

        with patch("app.graph.creation.nodes.get_default_llm", return_value=mock_llm):
            state: CreationState = {
                "topic": "人工智能",
                "description": None,
                "outline": [
                    {"title": "引言", "summary": "概述"},
                    {"title": "总结", "summary": "归纳"},
                ],
                "sections": [
                    {"title": "引言", "content": "引言内容", "index": 0},
                    {"title": "总结", "content": "总结内容", "index": 1},
                ],
                "final_draft": None,
                "messages": [],
                "current_node": "WriterNode",
                "error": None,
            }

            result = await reducer_node(state)

            assert "final_draft" in result
            assert "人工智能" in result["final_draft"]
            assert "messages" in result

    @pytest.mark.asyncio
    async def test_reducer_node_no_sections(self):
        """测试没有章节时的行为"""
        state: CreationState = {
            "topic": "测试主题",
            "description": None,
            "outline": [],
            "sections": [],
            "final_draft": None,
            "messages": [],
            "current_node": "WriterNode",
            "error": None,
        }

        result = await reducer_node(state)

        assert "final_draft" in result
        assert result["final_draft"] == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
