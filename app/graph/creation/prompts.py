"""Creation Graph 专属 Prompt 模板

本模块定义创作流程中各个节点的专属 Prompt 模板：
- PlannerNode: 生成结构化大纲
- WriterNode: 撰写单个章节
- ReducerNode: 合并章节并润色过渡段
"""

from app.graph.common.prompts import (
    CONTENT_STRATEGIST_ROLE,
    PROFESSIONAL_EDITOR_ROLE,
    PROFESSIONAL_WRITER_ROLE,
    create_base_system_prompt,
)

# ============================================
# PlannerNode Prompt 模板
# ============================================

PLANNER_SYSTEM_PROMPT = create_base_system_prompt(
    role=CONTENT_STRATEGIST_ROLE,
    task_description="""## 任务：生成结构化大纲

你的任务是根据用户提供的主题和描述，生成一份结构清晰、逻辑严密的文章大纲。

### 大纲要求

1. **章节划分**：将内容划分为 4-8 个章节，每个章节应有明确的主题
2. **逻辑顺序**：章节之间应有清晰的逻辑递进关系
3. **平衡性**：各章节的篇幅应大致均衡，避免某些章节过于冗长或简短
4. **完整性**：大纲应覆盖主题的所有重要方面，不遗漏关键内容

### 输出格式（严格遵守）

你必须且只能输出以下 JSON 格式，不要输出任何其他内容：

```json
{
  "outline": [
    {
      "title": "章节标题",
      "summary": "本章要点概述（2-3 句话）"
    }
  ]
}
```

**重要**：
- 顶层键必须是 "outline"，不能是 "sections" 或其他名称
- 每个章节对象必须包含 "title" 和 "summary" 两个字段
- "summary" 必须是字符串，不能是数组
- 只输出 JSON，不要输出任何解释文字""",
    include_markdown_rules=False,
    include_anti_hallucination=False,
    include_quality_standards=False,
)

PLANNER_HUMAN_PROMPT = """请根据以下主题生成文章大纲：

**主题**：{topic}

{description_section}

请严格按照以下 JSON 格式返回大纲（不要返回其他任何内容）：

```json
{{
  "outline": [
    {{"title": "章节标题", "summary": "本章要点概述"}},
    ...
  ]
}}
```"""

# ============================================
# WriterNode Prompt 模板
# ============================================

WRITER_SYSTEM_PROMPT = create_base_system_prompt(
    role=PROFESSIONAL_WRITER_ROLE,
    task_description="""## 任务：撰写章节内容

你的任务是根据给定的章节标题和摘要，撰写高质量的章节内容。

### 写作要求

1. **深度**：内容应有足够深度，提供有价值的见解和分析
2. **结构**：章节内部应有清晰的段落划分，每个段落围绕一个核心观点
3. **论据**：使用具体案例、数据或技术细节支撑论点
4. **可读性**：语言流畅自然，避免过于学术化的表达

### 内容长度

- 每个章节的目标字数：800-1500 字
- 段落数量：3-6 个段落
- 确保内容充实，避免过于简略

### 输出格式

直接输出章节内容，使用 Markdown 格式。章节标题使用二级标题（##），小节标题使用三级标题（###）。""",
    include_markdown_rules=True,
    include_anti_hallucination=True,
    include_quality_standards=True,
)

WRITER_HUMAN_PROMPT = """请撰写以下章节的内容：

**章节标题**：{section_title}

**章节摘要**：{section_summary}

**文章主题**：{topic}

**章节位置**：第 {section_index} 章（共 {total_sections} 章）

请直接输出章节内容，使用 Markdown 格式。"""

# ============================================
# ReducerNode Prompt 模板
# ============================================

REDUCER_SYSTEM_PROMPT = create_base_system_prompt(
    role=PROFESSIONAL_EDITOR_ROLE,
    task_description="""## 任务：合并章节并润色过渡段

你的任务是将多个独立撰写的章节合并成一篇完整的文章，并添加必要的过渡段落。

### 合并要求

1. **顺序整合**：按照章节顺序整合内容，确保逻辑连贯
2. **过渡段落**：在章节之间添加简短的过渡段落，使文章流畅自然
3. **统一风格**：检查并统一各章节的写作风格和术语使用
4. **去除冗余**：删除重复或冗余的内容
5. **添加开头**：撰写文章引言，概述全文主旨
6. **添加结尾**：撰写文章总结，归纳核心观点

### 过渡段落要求

- 长度：1-2 句话
- 作用：承上启下，提示读者即将进入新的主题
- 风格：自然流畅，不生硬

### 输出格式

输出完整的文章，使用 Markdown 格式。包括：
- 文章标题（一级标题）
- 引言段落
- 各章节内容（二级标题）
- 过渡段落
- 总结段落""",
    include_markdown_rules=True,
    include_anti_hallucination=True,
    include_quality_standards=True,
)

REDUCER_HUMAN_PROMPT = """请将以下章节合并成一篇完整的文章：

**文章主题**：{topic}

**章节内容**：
{sections_content}

请输出完整的文章，包括引言、各章节（添加过渡段落）和总结。"""

# ============================================
# 辅助函数
# ============================================


def format_sections_for_reducer(sections: list[dict]) -> str:
    """格式化章节内容供 ReducerNode 使用

    Args:
        sections: 章节内容列表，每个元素包含 title, content, index

    Returns:
        str: 格式化后的章节内容字符串
    """
    formatted_parts = []
    for section in sorted(sections, key=lambda x: x.get("index", 0)):
        formatted_parts.append(
            f"### 第 {section.get('index', 0)} 章：{section.get('title', '未命名')}\n\n"
            f"{section.get('content', '无内容')}\n"
        )
    return "\n---\n\n".join(formatted_parts)


def format_outline_for_display(outline: list[dict]) -> str:
    """格式化大纲用于显示

    Args:
        outline: 大纲列表，每个元素包含 title 和 summary

    Returns:
        str: 格式化后的大纲字符串
    """
    formatted_parts = []
    for idx, item in enumerate(outline, 1):
        formatted_parts.append(
            f"{idx}. **{item.get('title', '未命名')}**\n"
            f"   {item.get('summary', '无摘要')}"
        )
    return "\n".join(formatted_parts)
