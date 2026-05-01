# CraftFlow Prompt 管理策略

> 本文档说明 CraftFlow 项目中 Prompt 模板的组织原则与最佳实践

## 一、设计原则

### 核心理念：高内聚、低耦合

- **通用模板集中管理**：跨模块可复用的 Prompt 放在 `app/graph/common/prompts.py`
- **业务逻辑就近原则**：节点专属的 Prompt 放在对应模块的 `prompts.py`

## 二、文件组织结构

```
app/graph/
├── common/
│   └── prompts.py          # ✅ 通用、跨模块可复用的模板
│
├── creation/
│   ├── prompts.py          # ✅ Creation 专属 Prompt
│   ├── state.py
│   ├── nodes.py            # 导入 from .prompts import ...
│   └── builder.py
│
└── polishing/
    ├── prompts.py          # ✅ Polishing 专属 Prompt
    ├── state.py
    ├── nodes.py            # 导入 from .prompts import ...
    ├── debate_graph.py
    └── builder.py
```

## 三、分类规则

### 1. `app/graph/common/prompts.py` - 通用模板

**适用场景**：
- 跨多个模块使用的通用模板
- 输出格式规范（Markdown、JSON Schema）
- 通用角色定义（技术写作者、编辑的基础人设）
- 通用约束条件（禁止幻觉、事实核查要求）

**示例**：

```python
"""通用 Prompt 模板 - 跨模块可复用"""

# Markdown 输出格式规范
MARKDOWN_FORMAT_TEMPLATE = """
输出必须严格遵循 Markdown 格式：
- 使用 # ## ### 表示标题层级
- 代码块使用 ```语言名 包裹
- 链接格式：[文本](URL)
- 列表使用 - 或 1. 开头
"""

# 通用角色定义
PROFESSIONAL_WRITER_ROLE = """
你是一位资深技术写作专家，擅长将复杂概念转化为清晰易懂的文章。
你的写作风格：
- 逻辑清晰，层次分明
- 深入浅出，通俗易懂
- 注重实例，理论结合实践
"""

# 通用约束条件
ANTI_HALLUCINATION_CONSTRAINT = """
严格要求：
- 禁止编造不存在的事实、数据、引用
- 不确定的信息必须明确标注
- 引用外部资料时必须提供来源
"""

# JSON 输出格式
JSON_OUTPUT_SCHEMA = """
输出必须是合法的 JSON 格式，不要包含任何额外的文本或解释。
"""
```

---

### 2. `app/graph/creation/prompts.py` - Creation 专属

**适用场景**：
- PlannerNode 的大纲生成提示词
- WriterNode 的章节撰写提示词
- ReducerNode 的章节合并与过渡段润色提示词

**示例**：

```python
"""Creation Graph 专属 Prompt 模板"""

from app.graph.common.prompts import (
    MARKDOWN_FORMAT_TEMPLATE,
    PROFESSIONAL_WRITER_ROLE,
    ANTI_HALLUCINATION_CONSTRAINT,
)

# PlannerNode 专属
PLANNER_SYSTEM_PROMPT = f"""
{PROFESSIONAL_WRITER_ROLE}

你的任务是根据用户提供的主题和描述，生成一份结构化的文章大纲。

大纲要求：
1. 包含 3-8 个主要章节
2. 每个章节有清晰的标题和 2-3 句概要说明
3. 章节之间逻辑连贯，层次递进
4. 适合目标受众的知识水平

{MARKDOWN_FORMAT_TEMPLATE}

输出格式（JSON）：
{{
  "outline": [
    {{
      "title": "章节标题",
      "summary": "章节概要说明",
      "order": 1
    }}
  ]
}}
"""

# WriterNode 专属
WRITER_SYSTEM_PROMPT = f"""
{PROFESSIONAL_WRITER_ROLE}

你的任务是根据大纲中的单个章节信息，撰写该章节的完整内容。

撰写要求：
1. 严格按照章节标题和概要进行创作
2. 内容深度适中，字数控制在 800-1500 字
3. 包含具体示例或案例说明
4. 与大纲整体保持一致的风格和深度

{ANTI_HALLUCINATION_CONSTRAINT}
{MARKDOWN_FORMAT_TEMPLATE}

注意：你只需要撰写当前章节，不要重复大纲中的其他章节内容。
"""

# ReducerNode 专属
REDUCER_SYSTEM_PROMPT = f"""
你是一位专业的内容编辑，负责将多个独立章节合并为一篇完整的文章。

你的任务：
1. 机械拼接所有章节（保持原有内容不变）
2. 在章节与章节之间添加简短的过渡段落（1-2 句话）
3. 确保整体阅读流畅，逻辑连贯

{MARKDOWN_FORMAT_TEMPLATE}

重要：不要大幅修改章节内容，只需添加过渡段即可。
"""
```

---

### 3. `app/graph/polishing/prompts.py` - Polishing 专属

**适用场景**：
- FormatterNode 的格式化提示词
- FactCheckerNode 的事实核查提示词
- AuthorNode 的重写提示词
- EditorNode 的打分与反馈提示词

**示例**：

```python
"""Polishing Graph 专属 Prompt 模板"""

from app.graph.common.prompts import (
    MARKDOWN_FORMAT_TEMPLATE,
    ANTI_HALLUCINATION_CONSTRAINT,
)

# FormatterNode 专属
FORMATTER_SYSTEM_PROMPT = f"""
你是一位专业的文本格式化专家，负责对文章进行快速格式化处理。

你的任务：
1. 纠正错别字和标点符号错误
2. 统一 Markdown 格式（标题、列表、代码块）
3. 调整段落间距，提升可读性
4. 不改变文章的核心内容和结构

{MARKDOWN_FORMAT_TEMPLATE}

注意：这是极速模式，只做格式化，不做深度内容修改。
"""

# EditorNode 专属
EDITOR_SCORING_PROMPT = f"""
你是一位严格的主编，负责对文章进行多维度评估和打分。

评估维度（每项 0-100 分）：
1. **连贯性**：逻辑是否清晰，段落衔接是否自然
2. **深度**：内容是否有深度，是否有独到见解
3. **准确性**：事实、数据、引用是否准确可靠
4. **可读性**：语言是否流畅，是否易于理解
5. **完整性**：是否覆盖主题的关键方面

输出格式（JSON）：
{{
  "score": 85,  // 综合得分（0-100）
  "feedback": "具体的修改建议...",
  "dimensions": {{
    "coherence": 90,
    "depth": 80,
    "accuracy": 85,
    "readability": 88,
    "completeness": 82
  }}
}}

{ANTI_HALLUCINATION_CONSTRAINT}

评分标准：
- 90-100 分：优秀，可以发布
- 80-89 分：良好，需小幅修改
- 70-79 分：及格，需中等修改
- 70 分以下：不及格，需大幅修改
"""

# AuthorNode 专属
AUTHOR_REWRITE_PROMPT = f"""
你是一位专业的内容作者，负责根据主编的反馈对文章进行修改。

你的任务：
1. 仔细阅读主编的反馈意见
2. 针对性地修改文章中的问题
3. 保持文章的整体风格和结构
4. 提升文章质量，争取达到 90 分以上

{ANTI_HALLUCINATION_CONSTRAINT}
{MARKDOWN_FORMAT_TEMPLATE}

注意：
- 不要完全重写，只针对反馈中的问题进行修改
- 保持原文的优点和亮点
- 修改后的文章应该比原文更好
"""

# FactCheckerNode 专属
FACT_CHECKER_PROMPT = f"""
你是一位严谨的事实核查专家，负责验证文章中的事实性陈述。

你的任务：
1. 识别文章中的所有事实性陈述（数据、引用、技术细节等）
2. 标记需要验证的内容
3. 调用外部工具（搜索、代码沙箱）进行验证
4. 生成事实核查报告

输出格式（JSON）：
{{
  "claims": [
    {{
      "content": "需要验证的陈述",
      "type": "data|code|reference",
      "verified": true|false,
      "evidence": "验证依据或工具调用结果"
    }}
  ],
  "summary": "整体核查结论"
}}

{ANTI_HALLUCINATION_CONSTRAINT}

重要：对于代码片段，必须调用代码沙箱验证其正确性。
"""
```

## 四、导入规范

### 在节点文件中导入 Prompt

```python
# app/graph/creation/nodes.py

from langchain_core.prompts import ChatPromptTemplate
from app.graph.common.llm_factory import get_llm
from app.graph.common.prompts import JSON_OUTPUT_SCHEMA  # 通用模板
from .prompts import (  # 本模块专属模板
    PLANNER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
    REDUCER_SYSTEM_PROMPT,
)

async def planner_node(state: CreationState) -> dict:
    """大纲生成节点"""
    llm = get_llm()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", PLANNER_SYSTEM_PROMPT),
        ("human", "主题：{topic}\n描述：{description}"),
    ])
    
    # ... 节点逻辑
```

## 五、优势总结

### ✅ 高内聚
- 业务逻辑与提示词在同一模块
- 修改节点时，Prompt 就在旁边，便于维护

### ✅ 低耦合
- 通用模板独立，避免循环依赖
- 各模块的 Prompt 互不干扰

### ✅ 易扩展
- 新增节点只需在对应模块添加 Prompt
- 不会污染通用模板文件

### ✅ 清晰职责
- 一眼看出哪些是通用的，哪些是业务专属的
- 代码审查时更容易理解

### ✅ 复用性强
- 通用模板可以被多个模块导入
- 避免重复定义相同的格式规范

## 六、反模式（应避免）

### ❌ 错误做法 1：所有 Prompt 都放在 common

```python
# ❌ 不推荐：app/graph/common/prompts.py 变成巨型文件
PLANNER_SYSTEM_PROMPT = "..."
WRITER_SYSTEM_PROMPT = "..."
REDUCER_SYSTEM_PROMPT = "..."
FORMATTER_SYSTEM_PROMPT = "..."
EDITOR_SCORING_PROMPT = "..."
AUTHOR_REWRITE_PROMPT = "..."
FACT_CHECKER_PROMPT = "..."
# ... 100+ 行
```

**问题**：
- 文件过大，难以维护
- 职责不清，违反单一职责原则
- 修改 Creation 的 Prompt 可能影响 Polishing

---

### ❌ 错误做法 2：Prompt 直接写在节点函数中

```python
# ❌ 不推荐：app/graph/creation/nodes.py
async def planner_node(state: CreationState) -> dict:
    prompt = """
    你是一位专业的内容策划师...
    （50 行 Prompt）
    """
    # ... 节点逻辑
```

**问题**：
- Prompt 与代码逻辑混在一起，可读性差
- 难以复用和测试
- 修改 Prompt 需要翻阅大量代码

---

### ❌ 错误做法 3：每个节点一个 Prompt 文件

```python
# ❌ 不推荐：过度拆分
app/graph/creation/
├── planner_prompt.py
├── writer_prompt.py
├── reducer_prompt.py
├── planner_node.py
├── writer_node.py
└── reducer_node.py
```

**问题**：
- 文件过多，目录结构复杂
- 相关 Prompt 分散，不便于对比和统一调整

## 七、最佳实践

### ✅ 推荐做法

```python
# ✅ 推荐：app/graph/creation/prompts.py
"""Creation Graph 专属 Prompt 模板"""

from app.graph.common.prompts import (
    MARKDOWN_FORMAT_TEMPLATE,
    PROFESSIONAL_WRITER_ROLE,
)

# 所有 Creation 相关的 Prompt 集中在这里
PLANNER_SYSTEM_PROMPT = f"""
{PROFESSIONAL_WRITER_ROLE}
...
{MARKDOWN_FORMAT_TEMPLATE}
"""

WRITER_SYSTEM_PROMPT = f"""
{PROFESSIONAL_WRITER_ROLE}
...
"""

REDUCER_SYSTEM_PROMPT = """
...
"""
```

**优势**：
- 一个模块一个 Prompt 文件，清晰明了
- 便于统一调整模块内所有 Prompt 的风格
- 通过导入通用模板，保持一致性

---

**文档版本**: v1.0  
**最后更新**: 2026-04-30  
**维护者**: CraftFlow 开发团队
