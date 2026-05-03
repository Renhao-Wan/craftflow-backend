"""Polishing Graph 专属 Prompt 模板

本模块定义润色流程中各个节点的专属 Prompt 模板：
- RouterNode: 路由决策
- FormatterNode: 格式化内容
- FactCheckerNode: 事实核查
- AuthorNode: 重写内容
- EditorNode: 评分与反馈
"""

from app.graph.common.prompts import (
    ANTI_HALLUCINATION_RULES,
    MARKDOWN_FORMAT_RULES,
    PROFESSIONAL_EDITOR_ROLE,
    PROFESSIONAL_WRITER_ROLE,
    SEARCH_TOOL_USAGE_INSTRUCTION,
    create_base_system_prompt,
)

# ============================================
# RouterNode Prompt 模板
# ============================================

ROUTER_SYSTEM_PROMPT = """你是一位内容分析专家，负责分析文章内容并决定最佳的润色策略。

## 分析维度

请从以下维度评估文章：

1. **格式规范性**：Markdown 格式是否正确、标题层级是否合理
2. **内容准确性**：是否存在事实错误、数据过时、引用不准确
3. **语言质量**：表达是否流畅、逻辑是否清晰、用词是否准确

## 决策规则

- **模式 1（极速格式化）**：文章内容质量良好，仅需格式调整
- **模式 2（专家对抗审查）**：文章需要深度润色和质量提升
- **模式 3（事实核查）**：文章包含较多事实性内容，需要验证准确性

请以 JSON 格式输出分析结果：
```json
{
  "recommended_mode": 1,
  "analysis": {
    "format_score": 80,
    "accuracy_score": 90,
    "language_score": 85
  },
  "reason": "推荐理由"
}
```"""

ROUTER_HUMAN_PROMPT = """请分析以下文章内容，并推荐最佳的润色模式：

**文章内容**：
{content}

请以 JSON 格式返回分析结果。"""

# ============================================
# FormatterNode Prompt 模板
# ============================================

FORMATTER_SYSTEM_PROMPT = create_base_system_prompt(
    role=PROFESSIONAL_WRITER_ROLE,
    task_description="""## 任务：格式化文章内容

你的任务是对文章进行格式化处理，确保 Markdown 格式规范、排版美观。

### 格式化要求

1. **标题层级**：修正标题层级，确保逻辑清晰
2. **段落间距**：添加适当的空行，提高可读性
3. **列表格式**：统一列表符号和缩进
4. **代码块**：确保代码块语法正确
5. **链接格式**：修正链接格式
6. **表格格式**：优化表格显示

### 注意事项

- 保持原文内容不变，仅调整格式
- 不要添加或删除实质性内容
- 确保格式化后的文档结构清晰""",
    include_markdown_rules=True,
    include_anti_hallucination=False,
    include_quality_standards=False,
)

FORMATTER_HUMAN_PROMPT = """请对以下文章进行格式化处理：

**文章内容**：
{content}

请输出格式化后的完整文章。"""

# ============================================
# FactCheckerNode Prompt 模板
# ============================================

FACT_CHECKER_SYSTEM_PROMPT = create_base_system_prompt(
    role=PROFESSIONAL_EDITOR_ROLE,
    task_description="""## 任务：事实核查

你的任务是对文章中的事实性内容进行核查，识别并标注可能存在的问题。

### 核查范围

1. **数据准确性**：数字、统计数据、百分比是否准确
2. **时间准确性**：日期、年份、时间线是否正确
3. **引用准确性**：引用的理论、观点、名言是否准确
4. **技术准确性**：技术概念、API、工具名称是否正确
5. **逻辑一致性**：前后论述是否矛盾

### 输出格式

请以 JSON 格式输出核查结果：
```json
{
  "overall_accuracy": "high/medium/low",
  "issues": [
    {
      "type": "data/time/reference/technical/logic",
      "location": "问题所在段落或句子",
      "description": "问题描述",
      "suggestion": "修改建议"
    }
  ],
  "verified_facts": ["已验证的事实列表"],
  "summary": "核查总结"
}
```""",
    include_markdown_rules=False,
    include_anti_hallucination=True,
    additional_instructions=SEARCH_TOOL_USAGE_INSTRUCTION,
)

FACT_CHECKER_HUMAN_PROMPT = """请对以下文章进行事实核查：

**文章内容**：
{content}

请使用搜索工具验证关键事实，并以 JSON 格式返回核查结果。"""

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


def format_fact_check_result(result_data: dict) -> str:
    """格式化事实核查结果为可读文本

    Args:
        result_data: 核查结果数据

    Returns:
        str: 格式化后的核查结果
    """
    parts = []

    # 总体准确性
    accuracy = result_data.get("overall_accuracy", "unknown")
    parts.append(f"**总体准确性**：{accuracy}")

    # 问题列表
    issues = result_data.get("issues", [])
    if issues:
        parts.append("\n**发现的问题**：")
        for idx, issue in enumerate(issues, 1):
            parts.append(f"{idx}. **{issue.get('type', '未知')}** - {issue.get('location', '')}")
            parts.append(f"   问题：{issue.get('description', '')}")
            parts.append(f"   建议：{issue.get('suggestion', '')}")

    # 已验证事实
    verified = result_data.get("verified_facts", [])
    if verified:
        parts.append("\n**已验证事实**：")
        for fact in verified:
            parts.append(f"- {fact}")

    # 总结
    summary = result_data.get("summary", "")
    if summary:
        parts.append(f"\n**总结**：{summary}")

    return "\n".join(parts)
