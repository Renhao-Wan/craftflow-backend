"""Polishing Graph 状态定义测试

测试 PolishingState 和 DebateState 的类型定义和结构。
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.graph.polishing.state import (
    DebateRound,
    PolishingState,
    ScoreDetail,
)
from app.graph.polishing.debate.state import DebateState


# ============================================
# 辅助类型测试
# ============================================


class TestScoreDetail:
    """测试 ScoreDetail 类型"""

    def test_score_detail_creation(self):
        """测试创建 ScoreDetail"""
        score: ScoreDetail = {
            "dimension": "逻辑性",
            "score": 85.0,
            "comment": "逻辑清晰，论证充分"
        }

        assert score["dimension"] == "逻辑性"
        assert score["score"] == 85.0
        assert score["comment"] == "逻辑清晰，论证充分"

    def test_score_detail_fields(self):
        """测试 ScoreDetail 字段类型"""
        score: ScoreDetail = {
            "dimension": "可读性",
            "score": 90.5,
            "comment": "语言流畅"
        }

        assert isinstance(score["dimension"], str)
        assert isinstance(score["score"], float)
        assert isinstance(score["comment"], str)


class TestDebateRound:
    """测试 DebateRound 类型"""

    def test_debate_round_creation(self):
        """测试创建 DebateRound"""
        round_data: DebateRound = {
            "round_number": 1,
            "author_content": "重写后的内容...",
            "editor_feedback": "需要改进...",
            "editor_score": 75.0
        }

        assert round_data["round_number"] == 1
        assert round_data["author_content"] == "重写后的内容..."
        assert round_data["editor_feedback"] == "需要改进..."
        assert round_data["editor_score"] == 75.0


# ============================================
# PolishingState 测试
# ============================================


class TestPolishingState:
    """测试 PolishingState 类型"""

    def test_polishing_state_creation(self):
        """测试创建 PolishingState"""
        state: PolishingState = {
            "content": "# 测试文章\n\n内容...",
            "mode": 2,
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

        assert state["content"] == "# 测试文章\n\n内容..."
        assert state["mode"] == 2
        assert state["current_node"] is None
        assert state["error"] is None

    def test_polishing_state_mode_values(self):
        """测试 PolishingState 的 mode 字段"""
        # Mode 1: 极速格式化
        state1: PolishingState = {
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
        assert state1["mode"] == 1

        # Mode 2: 专家对抗审查
        state2: PolishingState = {
            "content": "测试内容",
            "mode": 2,
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
        assert state2["mode"] == 2

        # Mode 3: 事实核查
        state3: PolishingState = {
            "content": "测试内容",
            "mode": 3,
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
        assert state3["mode"] == 3

    def test_polishing_state_with_messages(self):
        """测试 PolishingState 的消息累加"""
        state: PolishingState = {
            "content": "测试内容",
            "mode": 2,
            "current_node": None,
            "error": None,
            "formatted_content": None,
            "fact_check_result": None,
            "debate_history": [],
            "final_content": None,
            "scores": [],
            "overall_score": None,
            "messages": [AIMessage(content="消息1")],
        }

        # 模拟 reducer 行为
        new_messages = [AIMessage(content="消息2")]
        # 在实际 LangGraph 中，operator.add 会自动累加
        combined = state["messages"] + new_messages
        assert len(combined) == 2

    def test_polishing_state_with_debate_history(self):
        """测试 PolishingState 的对抗历史"""
        history: list[DebateRound] = [
            {
                "round_number": 1,
                "author_content": "第一轮内容",
                "editor_feedback": "第一轮反馈",
                "editor_score": 70.0,
            },
            {
                "round_number": 2,
                "author_content": "第二轮内容",
                "editor_feedback": "第二轮反馈",
                "editor_score": 85.0,
            },
        ]

        state: PolishingState = {
            "content": "测试内容",
            "mode": 2,
            "current_node": None,
            "error": None,
            "formatted_content": None,
            "fact_check_result": None,
            "debate_history": history,
            "final_content": None,
            "scores": [],
            "overall_score": None,
            "messages": [],
        }

        assert len(state["debate_history"]) == 2
        assert state["debate_history"][0]["round_number"] == 1
        assert state["debate_history"][1]["editor_score"] == 85.0

    def test_polishing_state_with_scores(self):
        """测试 PolishingState 的评分"""
        scores: list[ScoreDetail] = [
            {"dimension": "逻辑性", "score": 85.0, "comment": "逻辑清晰"},
            {"dimension": "可读性", "score": 90.0, "comment": "语言流畅"},
            {"dimension": "准确性", "score": 95.0, "comment": "事实准确"},
        ]

        state: PolishingState = {
            "content": "测试内容",
            "mode": 2,
            "current_node": None,
            "error": None,
            "formatted_content": None,
            "fact_check_result": None,
            "debate_history": [],
            "final_content": None,
            "scores": scores,
            "overall_score": 90.0,
            "messages": [],
        }

        assert len(state["scores"]) == 3
        assert state["overall_score"] == 90.0


# ============================================
# DebateState 测试
# ============================================


class TestDebateState:
    """测试 DebateState 类型"""

    def test_debate_state_creation(self):
        """测试创建 DebateState"""
        state: DebateState = {
            "content": "待润色内容",
            "topic": "测试主题",
            "current_iteration": 0,
            "max_iterations": 3,
            "pass_score": 90.0,
            "author_output": None,
            "editor_feedback": None,
            "editor_score": 0.0,
            "debate_history": [],
            "final_content": None,
            "is_passed": False,
            "messages": [],
            "error": None,
        }

        assert state["content"] == "待润色内容"
        assert state["topic"] == "测试主题"
        assert state["current_iteration"] == 0
        assert state["max_iterations"] == 3
        assert state["pass_score"] == 90.0
        assert state["is_passed"] is False

    def test_debate_state_iteration_control(self):
        """测试 DebateState 的迭代控制"""
        state: DebateState = {
            "content": "测试内容",
            "topic": None,
            "current_iteration": 2,
            "max_iterations": 3,
            "pass_score": 90.0,
            "author_output": "重写内容",
            "editor_feedback": "需要改进",
            "editor_score": 85.0,
            "debate_history": [],
            "final_content": None,
            "is_passed": False,
            "messages": [],
            "error": None,
        }

        # 模拟迭代增加
        state["current_iteration"] += 1
        assert state["current_iteration"] == 3

        # 检查是否达到最大迭代
        should_continue = state["current_iteration"] < state["max_iterations"]
        assert should_continue is False

    def test_debate_state_pass_condition(self):
        """测试 DebateState 的通过条件"""
        state: DebateState = {
            "content": "测试内容",
            "topic": None,
            "current_iteration": 1,
            "max_iterations": 3,
            "pass_score": 90.0,
            "author_output": "高质量内容",
            "editor_feedback": "优秀",
            "editor_score": 95.0,
            "debate_history": [],
            "final_content": None,
            "is_passed": False,
            "messages": [],
            "error": None,
        }

        # 检查是否通过评分
        is_passed = state["editor_score"] >= state["pass_score"]
        assert is_passed is True

    def test_debate_state_with_history(self):
        """测试 DebateState 的历史记录"""
        history: list[DebateRound] = [
            {
                "round_number": 1,
                "author_content": "第一轮重写",
                "editor_feedback": "需要更多细节",
                "editor_score": 70.0,
            },
        ]

        state: DebateState = {
            "content": "测试内容",
            "topic": None,
            "current_iteration": 1,
            "max_iterations": 3,
            "pass_score": 90.0,
            "author_output": "第二轮重写",
            "editor_feedback": "有进步",
            "editor_score": 85.0,
            "debate_history": history,
            "final_content": None,
            "is_passed": False,
            "messages": [],
            "error": None,
        }

        # 模拟添加新轮次
        new_round: DebateRound = {
            "round_number": 2,
            "author_content": state["author_output"],
            "editor_feedback": state["editor_feedback"],
            "editor_score": state["editor_score"],
        }
        combined_history = state["debate_history"] + [new_round]

        assert len(combined_history) == 2
        assert combined_history[1]["round_number"] == 2

    def test_debate_state_error_handling(self):
        """测试 DebateState 的错误处理"""
        state: DebateState = {
            "content": "测试内容",
            "topic": None,
            "current_iteration": 1,
            "max_iterations": 3,
            "pass_score": 90.0,
            "author_output": None,
            "editor_feedback": None,
            "editor_score": 0.0,
            "debate_history": [],
            "final_content": None,
            "is_passed": False,
            "messages": [],
            "error": "LLM API 调用失败",
        }

        assert state["error"] is not None
        assert "失败" in state["error"]


# ============================================
# 集成测试
# ============================================


class TestStateIntegration:
    """测试状态的集成功能"""

    def test_polishing_to_debate_state_conversion(self):
        """测试从 PolishingState 转换到 DebateState"""
        polishing_state: PolishingState = {
            "content": "原始内容",
            "mode": 2,
            "current_node": "router",
            "error": None,
            "formatted_content": None,
            "fact_check_result": None,
            "debate_history": [],
            "final_content": None,
            "scores": [],
            "overall_score": None,
            "messages": [HumanMessage(content="开始润色")],
        }

        # 模拟转换到 DebateState
        debate_state: DebateState = {
            "content": polishing_state["content"],
            "topic": None,
            "current_iteration": 0,
            "max_iterations": 3,
            "pass_score": 90.0,
            "author_output": None,
            "editor_feedback": None,
            "editor_score": 0.0,
            "debate_history": [],
            "final_content": None,
            "is_passed": False,
            "messages": polishing_state["messages"],
            "error": None,
        }

        assert debate_state["content"] == polishing_state["content"]
        assert debate_state["messages"] == polishing_state["messages"]

    def test_debate_to_polishing_state_conversion(self):
        """测试从 DebateState 转换回 PolishingState"""
        debate_state: DebateState = {
            "content": "原始内容",
            "topic": "测试主题",
            "current_iteration": 2,
            "max_iterations": 3,
            "pass_score": 90.0,
            "author_output": "最终润色内容",
            "editor_feedback": "优秀",
            "editor_score": 95.0,
            "debate_history": [],
            "final_content": "最终润色内容",
            "is_passed": True,
            "messages": [],
            "error": None,
        }

        # 模拟转换回 PolishingState
        polishing_state: PolishingState = {
            "content": "原始内容",
            "mode": 2,
            "current_node": "debate_complete",
            "error": None,
            "formatted_content": None,
            "fact_check_result": None,
            "debate_history": debate_state["debate_history"],
            "final_content": debate_state["final_content"],
            "scores": [],
            "overall_score": debate_state["editor_score"],
            "messages": debate_state["messages"],
        }

        assert polishing_state["final_content"] == "最终润色内容"
        assert polishing_state["overall_score"] == 95.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
