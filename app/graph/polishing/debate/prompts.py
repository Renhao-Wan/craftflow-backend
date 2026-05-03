"""Debate Subgraph 专属 Prompt 模板

本模块定义 Author-Editor 对抗循环中的 Prompt 模板：
- AuthorNode: 重写与润色文章
- EditorNode: 多维度评估与打分
"""

from app.graph.common.prompts import (
    PROFESSIONAL_WRITER_ROLE,
    create_base_system_prompt,
)

# ============================================
# AuthorNode Prompt 模板
# ============================================

AUTHOR_SYSTEM_PROMPT = create_base_system_prompt(
    role=PROFESSIONAL_WRITER_ROLE,
    task_description="""## 任务：重写与润色文章

你的任务是根据编辑的反馈，对文章进行深度润色和重写。

### 润色要求

1. **语言优化**：提升表达的流畅性和专业性
2. **逻辑优化**：加强段落之间的逻辑连接
3. **内容补充**：补充必要的细节和论据
4. **结构调整**：优化段落和章节结构
5. **风格统一**：确保全文风格一致

### 编辑反馈处理

请认真阅读编辑的反馈意见，并针对性地进行改进：
- 优先处理高优先级问题
- 保留文章的核心观点和主要论据
- 在改进的同时保持文章的完整性""",
    include_markdown_rules=True,
    include_anti_hallucination=True,
    include_quality_standards=True,
)

AUTHOR_HUMAN_PROMPT = """请根据以下反馈对文章进行润色：

**原始内容**：
{content}

**编辑反馈**：
{editor_feedback}

**当前评分**：{editor_score}/100

请输出润色后的完整文章。"""

# ============================================
# EditorNode Prompt 模板
# ============================================

EDITOR_SYSTEM_PROMPT = """你是一位严格的主编，负责对文章进行多维度评估和打分。

## 评分维度（总分 100 分）

1. **逻辑性（25 分）**
   - 论点是否明确
   - 论证是否充分
   - 前后是否连贯

2. **可读性（25 分）**
   - 语言是否流畅
   - 段落是否合理
   - 格式是否规范

3. **准确性（25 分）**
   - 事实是否正确
   - 数据是否可靠
   - 引用是否准确

4. **专业性（25 分）**
   - 内容是否深入
   - 术语是否规范
   - 观点是否独到

## 输出格式

请以 JSON 格式输出评估结果：
```json
{
  "scores": [
    {"dimension": "逻辑性", "score": 22, "comment": "论证充分，但部分段落衔接可优化"},
    {"dimension": "可读性", "score": 20, "comment": "语言流畅，但段落略长"},
    {"dimension": "准确性", "score": 23, "comment": "事实准确，引用规范"},
    {"dimension": "专业性", "score": 21, "comment": "内容深入，术语使用恰当"}
  ],
  "total_score": 86,
  "feedback": "详细的改进建议...",
  "highlights": ["亮点1", "亮点2"],
  "improvements": ["改进1", "改进2"]
}
```"""

EDITOR_HUMAN_PROMPT = """请对以下文章进行评估和打分：

**文章内容**：
{content}

**当前迭代**：第 {iteration} 轮

请以 JSON 格式返回评估结果。"""

# ============================================
# 辅助函数
# ============================================


def format_editor_feedback(feedback_data: dict) -> str:
    """格式化编辑反馈为可读文本

    Args:
        feedback_data: 编辑反馈数据

    Returns:
        str: 格式化后的反馈文本
    """
    parts = []

    # 总分
    total_score = feedback_data.get("total_score", 0)
    parts.append(f"**综合评分**：{total_score}/100")

    # 各维度评分
    scores = feedback_data.get("scores", [])
    if scores:
        parts.append("\n**维度评分**：")
        for score in scores:
            parts.append(f"- {score.get('dimension', '未知')}：{score.get('score', 0)} 分 - {score.get('comment', '')}")

    # 亮点
    highlights = feedback_data.get("highlights", [])
    if highlights:
        parts.append("\n**亮点**：")
        for h in highlights:
            parts.append(f"- {h}")

    # 改进建议
    improvements = feedback_data.get("improvements", [])
    if improvements:
        parts.append("\n**改进建议**：")
        for imp in improvements:
            parts.append(f"- {imp}")

    # 详细反馈
    feedback = feedback_data.get("feedback", "")
    if feedback:
        parts.append(f"\n**详细反馈**：\n{feedback}")

    return "\n".join(parts)
