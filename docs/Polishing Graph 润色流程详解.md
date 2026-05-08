# Polishing Graph 润色流程详解

## 概述

Polishing Graph 是 CraftFlow 的智能润色系统，提供三档润色模式，满足不同质量需求的文本处理场景。系统采用 LangGraph 状态机架构，支持条件路由和子图嵌套。

## 三种润色模式

| 模式 | 名称 | 适用场景 | 处理方式 |
|------|------|----------|----------|
| Mode 1 | 极速格式化 | 文章内容质量良好，仅需格式调整 | LLM 格式化 |
| Mode 2 | 专家对抗审查 | 文章需要深度润色和质量提升 | Author-Editor 博弈 |
| Mode 3 | 事实核查 | 文章包含较多事实性内容，需要验证准确性 | 搜索工具核查 + 条件修正 |

---

## Mode 1：极速格式化

### 功能说明

对文章进行格式化处理，确保 Markdown 格式规范、排版美观。**不修改文章内容**，仅调整格式。

### 处理范围

- 标题层级：修正标题层级，确保逻辑清晰
- 段落间距：添加适当的空行，提高可读性
- 列表格式：统一列表符号和缩进
- 代码块：确保代码块语法正确
- 链接格式：修正链接格式
- 表格格式：优化表格显示

### 执行流程

```
START → router → formatter → END
```

### 输出

- `formatted_content`：格式化后的文章内容
- `final_content`：同 `formatted_content`

---

## Mode 2：专家对抗审查

### 功能说明

采用 Author-Editor 博弈机制，通过多轮对抗迭代提升文章质量。Author 负责重写，Editor 负责评分和反馈，循环直至达标或达到最大轮次。

### 对抗参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_iterations` | 3 | 最大对抗轮次 |
| `pass_score` | 90 | 通过分数（满分 100） |

### 评分维度

Editor 从以下四个维度进行评分（每项 25 分，满分 100）：

1. **逻辑性**：论述是否严密、推理是否合理
2. **可读性**：语言是否流畅、表达是否清晰
3. **准确性**：事实是否准确、数据是否可靠
4. **专业性**：内容是否深入、术语是否规范

### 执行流程

```
START → router → debate → END
                ↓
        ┌───────────────────────────────────────┐
        │         Debate Subgraph               │
        │                                       │
        │   author → editor → should_continue   │
        │      ↑                    │           │
        │      │    ┌───────────────┘           │
        │      │    ↓                           │
        │      │  is_passed=True? ──→ end       │
        │      │  max_iterations? ──→ end       │
        │      │    │                           │
        │      └────┘ (继续下一轮)               │
        │                                       │
        │   finalize_debate                     │
        └───────────────────────────────────────┘
```

### 输出

- `final_content`：最终润色后的文章
- `debate_history`：每轮对抗记录（作者内容摘要、编辑反馈、评分）
- `overall_score`：最终评分

---

## Mode 3：事实核查

### 功能说明

对文章中的事实性内容进行核查，通过搜索工具验证关键事实。核查完成后根据准确性等级决定后续处理。

### 核查范围

1. **数据准确性**：数字、统计数据、百分比是否准确
2. **时间准确性**：日期、年份、时间线是否正确
3. **引用准确性**：引用的理论、观点、名言是否准确
4. **技术准确性**：技术概念、API、工具名称是否正确
5. **逻辑一致性**：前后论述是否矛盾

### Agent Loop 机制

FactCheckerNode 采用 Agent Loop 模式，支持多轮工具调用：

```
LLM 分析 → 发起搜索工具调用 → 执行搜索 → 结果喂回 LLM → 重复
                                                      ↓
                                              无工具调用时结束
```

- 最大工具调用轮次：3 轮
- 工具集：Tavily 搜索引擎

### 三种准确性等级

| 等级 | 标识 | 含义 | 后续行为 |
|------|------|------|----------|
| **high** | 高准确性 | 文章内容整体准确，未发现明显事实错误 | 直接返回原文，不进入修正流程 |
| **medium** | 中等准确性 | 文章存在部分事实问题 | 进入 Mode 2 对抗审查进行修正 |
| **low** | 低准确性 | 文章存在较多事实错误 | **强制**进入 Mode 2 对抗审查进行修正 |

### 准确性判定逻辑

```python
# 核查结果中的 overall_accuracy 字段
needs_revision = overall_accuracy != "high"

# 路由决策
if overall_accuracy == "low":
    return "debate"       # 强制进入修正
elif needs_revision:      # medium
    return "debate"       # 进入修正
else:                     # high
    return "end"          # 直接结束
```

### 执行流程

```
START → router → fact_checker → route_after_fact_check → END
                                    │
                                    ├─ overall_accuracy = "high"  → END（返回原文）
                                    │
                                    └─ overall_accuracy != "high"
                                         │
                                         ├─ "low"    → debate → END（强制修正）
                                         └─ "medium" → debate → END（进入修正）
```

### 输出

- `fact_check_result`：格式化的核查报告（存储于 `description` 字段）
- `final_content`：
  - high 等级：返回原始文章内容
  - medium/low 等级：返回对抗审查后的修正文章
- `needs_revision`：是否进入修正流程

### 核查报告格式

```markdown
**总体准确性**：medium

**发现的问题**：
1. **data** - 第二段统计数据
   问题：2023 年 GDP 数据与官方公布不符
   建议：核实国家统计局官方数据

2. **reference** - 名言引用
   问题：该名言出处存疑
   建议：标注"待核实"或移除

**已验证事实**：
- 技术概念描述准确
- 时间线梳理正确

**总结**：文章整体质量良好，存在 2 处数据问题需要修正。
```

---

## 图结构总览

```
                        ┌─────────────────────────────────────────┐
                        │           Polishing Graph               │
                        │                                         │
START ──────────────────→ router                                  │
                        │    │                                    │
                        │    ├─ mode=1 ──→ formatter ──→ END      │
                        │    │                                    │
                        │    ├─ mode=2 ──→ debate ──→ END         │
                        │    │              ↑                     │
                        │    │              │                     │
                        │    └─ mode=3 ──→ fact_checker           │
                        │                      │                  │
                        │                      ↓                  │
                        │              route_after_fact_check      │
                        │                      │                  │
                        │         ┌────────────┴────────────┐    │
                        │         ↓                         ↓    │
                        │    high/END               medium,low    │
                        │                              │          │
                        │                              ↓          │
                        │                           debate        │
                        │                              │          │
                        │                              ↓          │
                        │                             END         │
                        └─────────────────────────────────────────┘
```

---

## 状态定义

### PolishingState（主图状态）

| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | 输入文章内容 |
| `mode` | `Literal[1, 2, 3]` | 润色模式 |
| `current_node` | `Optional[str]` | 当前执行节点 |
| `error` | `Optional[str]` | 错误信息 |
| `needs_revision` | `bool` | Mode 3 是否需要修正 |
| `formatted_content` | `Optional[str]` | Mode 1 格式化结果 |
| `fact_check_result` | `Optional[str]` | Mode 3 核查报告 |
| `debate_history` | `list[DebateRound]` | 对抗历史记录 |
| `final_content` | `Optional[str]` | 最终输出内容 |
| `scores` | `list[ScoreDetail]` | 评分详情 |
| `overall_score` | `Optional[float]` | 总体评分 |
| `messages` | `list[BaseMessage]` | 消息流（reducer: add） |

### DebateState（对抗子图状态）

| 字段 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | 输入文章内容 |
| `fact_check_result` | `Optional[str]` | 核查报告（Mode 3 传入） |
| `current_iteration` | `int` | 当前轮次 |
| `max_iterations` | `int` | 最大轮次（默认 3） |
| `pass_score` | `float` | 通过分数（默认 90） |
| `author_output` | `Optional[str]` | Author 重写输出 |
| `editor_feedback` | `Optional[str]` | Editor 反馈 |
| `editor_score` | `float` | Editor 评分 |
| `debate_history` | `list[DebateRound]` | 对抗历史（reducer: add） |
| `final_content` | `Optional[str]` | 最终内容 |
| `is_passed` | `bool` | 是否通过评分 |

---

## 数据流转

### Mode 1 数据流

```
输入: content
  ↓
router_node: mode=1
  ↓
formatter_node: LLM 格式化
  ↓
输出: formatted_content, final_content
```

### Mode 2 数据流

```
输入: content
  ↓
router_node: mode=2
  ↓
debate_node:
  ├─ author_node: 首次重写
  ├─ editor_node: 评分 85 分
  ├─ should_continue: 85 < 90，继续
  ├─ author_node: 根据反馈二次重写
  ├─ editor_node: 评分 92 分
  └─ should_continue: 92 >= 90，结束
  ↓
finalize_debate_node
  ↓
输出: final_content, debate_history, overall_score
```

### Mode 3（high）数据流

```
输入: content
  ↓
router_node: mode=3
  ↓
fact_checker_node:
  ├─ LLM 分析 → 搜索工具调用 → 核查结果
  └─ overall_accuracy = "high"
  ↓
route_after_fact_check: high → END
  ↓
输出: fact_check_result, final_content=content（原文）
```

### Mode 3（medium/low）数据流

```
输入: content
  ↓
router_node: mode=3
  ↓
fact_checker_node:
  ├─ LLM 分析 → 搜索工具调用 → 核查结果
  └─ overall_accuracy = "medium"
  ↓
route_after_fact_check: medium → debate
  ↓
debate_node:
  ├─ author_node: 参考核查报告修正
  ├─ editor_node: 评分
  └─ should_continue: 达标或最大轮次
  ↓
finalize_debate_node
  ↓
输出: fact_check_result, final_content（修正后文章）, debate_history
```

---

## 存储说明

| 数据 | 存储位置 | 说明 |
|------|----------|------|
| 任务元数据 | SQLite `tasks` 表 | 包含 task_id, status, result 等 |
| 核查报告 | SQLite `tasks.description` 字段 | Mode 3 专用 |
| 原始内容 | SQLite `tasks.content` 字段 | 润色前的文章 |
| 润色模式 | SQLite `tasks.mode` 字段 | 1/2/3 |
| 最终结果 | SQLite `tasks.result` 字段 | 润色后的文章 |

---

## 前端展示

### 结果页面三个视图

1. **结果**：展示润色后的文章内容
2. **对比**：左右双栏对比原文和润色后内容
3. **核查报告**：仅 Mode 3 可用，展示事实核查详情

### 准确性摘要卡片（Mode 3 专属）

- **high**：绿色卡片，显示"高准确性"，说明"文章内容整体准确，未发现明显事实错误，因此直接返回原文。"
- **medium**：黄色卡片，显示"中等准确性"，说明"文章存在部分事实问题，已进入修正流程进行优化。"
- **low**：红色卡片，显示"低准确性"，说明"文章存在较多事实错误，已强制进入修正流程进行修正。"
