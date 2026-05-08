# Creation Graph 创作流程详解

## 概述

Creation Graph 是 CraftFlow 的智能长文创作系统，采用 **大纲先行 + Map-Reduce 并发撰写 + 人工确认** 的三阶段架构。系统通过 LangGraph 状态机实现，支持 Human-in-the-Loop（HITL）中断恢复机制。

## 核心特性

| 特性 | 说明 |
|------|------|
| 大纲先行 | LLM 先生成结构化大纲，用户确认后再撰写 |
| HITL 中断 | 大纲生成后暂停，等待用户确认或修改 |
| Map-Reduce 并发 | 多个章节并行撰写，提升效率 |
| 自动合并 | ReducerNode 统一合并章节，添加过渡段落 |

---

## 三个核心节点

### 1. PlannerNode（大纲规划）

**职责**：根据用户提供的主题和描述，生成结构化文章大纲。

**输入**：
- `topic`：创作主题（必填）
- `description`：创作描述（可选，补充说明）

**输出**：
- `outline`：大纲列表，每个条目包含 `title` 和 `summary`

**大纲规范**：
- 章节数量：4-8 个章节
- 逻辑顺序：章节之间有清晰的逻辑递进
- 平衡性：各章节篇幅大致均衡
- 完整性：覆盖主题的所有重要方面

**输出格式**：
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

**容错机制**：
- JSON 解析失败时，使用默认四段式大纲（引言、核心内容、实践应用、总结）
- 支持多种 JSON 格式变体（`outline`、`sections`、`heading` 等字段名）

---

### 2. WriterNode（章节撰写）

**职责**：根据大纲中的章节信息，生成单个章节的完整内容。

**设计特点**：
- **可并发执行**：通过 LangGraph 的 Send API 实现多个 WriterNode 实例并行运行
- **独立工作**：每个 WriterNode 只负责一个章节，互不依赖
- **自动合并**：通过 `sections` 字段的 `operator.add` reducer 自动合并结果

**输入**：
- `topic`：文章主题
- `outline`：完整大纲
- `sections`：已生成的章节列表（用于确定当前章节索引）

**输出**：
- `sections`：追加一个 `SectionContent` 对象

**写作规范**：
- 目标字数：800-1500 字/章节
- 段落数量：3-6 个段落
- 内容要求：有深度、有论据、可读性强
- 格式：Markdown，二级标题为章节标题，三级标题为小节标题

---

### 3. ReducerNode（合并润色）

**职责**：将所有独立撰写的章节合并成一篇完整的文章，添加引言、过渡段落和总结。

**输入**：
- `topic`：文章主题
- `sections`：所有章节内容列表

**输出**：
- `final_draft`：最终完整的文章

**合并任务**：
1. **顺序整合**：按照章节顺序整合内容
2. **过渡段落**：在章节之间添加 1-2 句过渡语
3. **统一风格**：检查并统一写作风格和术语使用
4. **去除冗余**：删除重复或冗余的内容
5. **添加开头**：撰写文章引言，概述全文主旨
6. **添加结尾**：撰写文章总结，归纳核心观点

---

## HITL 中断机制

### 中断点位置

```
START → planner → [interrupt_before] outline_confirmation → fan_out writers → reducer → END
                    ↑
                    │
              用户在此确认大纲
```

图编译时配置 `interrupt_before=["outline_confirmation"]`，当执行到 `outline_confirmation` 节点前自动暂停。

### 中断状态

任务进入 `interrupted` 状态后：
- 任务元数据保留在内存 `_tasks` dict 中
- 任务信息持久化到 SQLite（status="interrupted"）
- Checkpoint 数据保留（用于恢复时读取图状态）

### 恢复动作

| 动作 | 说明 |
|------|------|
| `confirm_outline` | 确认大纲，继续执行 |
| `update_outline` | 修改大纲后继续执行 |

**恢复流程**：
```python
# 确认大纲（直接恢复）
await graph.ainvoke(Command(resume=True), config)

# 修改大纲后恢复
await graph.aupdate_state(config, {"outline": new_outline})
await graph.ainvoke(Command(resume=True), config)
```

---

## Map-Reduce 并发模式

### 扇出机制

`_fan_out_writers` 函数使用 LangGraph 的 Send API 实现章节并发撰写：

```python
def _fan_out_writers(state: CreationState) -> list[Send]:
    outline = state.get("outline", [])
    sends = []
    for i in range(len(outline)):
        writer_state = {
            "topic": state.get("topic", ""),
            "outline": outline,
            "sections": [{"title": outline[j]["title"], "content": "", "index": j} for j in range(i)],
            ...
        }
        sends.append(Send("writer", writer_state))
    return sends
```

### 并发执行

- 每个章节独立启动一个 WriterNode 实例
- 所有 WriterNode 并行执行，互不阻塞
- 通过 `sections` 字段的 `operator.add` reducer 自动合并结果

### 合并流程

```
WriterNode_0 ──→ sections: [章节0] ──┐
WriterNode_1 ──→ sections: [章节1] ──┤
WriterNode_2 ──→ sections: [章节2] ──┼──→ reducer → final_draft
WriterNode_3 ──→ sections: [章节3] ──┤
         ...                         │
                                    ┘
                           operator.add 自动合并
```

---

## 执行流程

### 完整流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Creation Graph                                  │
│                                                                         │
│  START                                                                  │
│    │                                                                    │
│    ▼                                                                    │
│  ┌─────────────┐                                                        │
│  │   planner   │  ← LLM 生成大纲                                        │
│  └──────┬──────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────────┐                                                │
│  │ outline_confirmation │  ← HITL 中断点                                │
│  │    (interrupt_before)│     用户确认/修改大纲                          │
│  └──────┬──────────────┘                                                │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────────────────────────────────────────────────────┐       │
│  │                    fan_out_writers                           │       │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │       │
│  │  │ writer_0│ │ writer_1│ │ writer_2│ │ writer_3│  ...       │       │
│  │  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘           │       │
│  │       │           │           │           │                 │       │
│  │       └───────────┴───────────┴───────────┘                 │       │
│  │                       │                                     │       │
│  │                       ▼                                     │       │
│  │              sections 自动合并                              │       │
│  └──────────────────────────────────────────────────────────────┘       │
│                         │                                               │
│                         ▼                                               │
│                  ┌─────────────┐                                        │
│                  │   reducer   │  ← 合并章节、添加过渡段落               │
│                  └──────┬──────┘                                        │
│                         │                                               │
│                         ▼                                               │
│                        END                                              │
│                          │                                              │
│                          ▼                                              │
│                    final_draft                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 状态流转

```
                    ┌──────────────────────────────────────┐
                    │            状态流转                    │
                    └──────────────────────────────────────┘

    ┌─────────┐      ┌─────────┐      ┌─────────────┐      ┌─────────┐
    │ running │ ───→ │interrupted│ ───→│  running    │ ───→ │completed│
    └─────────┘      └─────────┘      └─────────────┘      └─────────┘
         │                                   │                   │
         │                                   │                   │
         ▼                                   ▼                   ▼
    planner_node                     resume_task()          final_draft
    生成大纲                         恢复执行               最终文章
```

---

## 状态定义

### CreationState

| 字段 | 类型 | 说明 |
|------|------|------|
| `topic` | `str` | 创作主题 |
| `description` | `Optional[str]` | 创作描述 |
| `outline` | `list[OutlineItem]` | 大纲列表 |
| `sections` | `Annotated[list[SectionContent], operator.add]` | 章节内容（reducer: add） |
| `final_draft` | `Optional[str]` | 最终文章 |
| `messages` | `Annotated[list[BaseMessage], operator.add]` | 消息流（reducer: add） |
| `current_node` | `Optional[str]` | 当前执行节点 |
| `error` | `Optional[str]` | 错误信息 |

### OutlineItem

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | `str` | 章节标题 |
| `summary` | `str` | 章节摘要 |

### SectionContent

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | `str` | 章节标题 |
| `content` | `str` | 章节内容 |
| `index` | `int` | 章节索引 |

---

## 数据流转

### 正常流程（无中断）

```
输入: topic="AI 发展趋势", description="探讨人工智能未来发展方向"
  ↓
planner_node: LLM 生成大纲
  ↓
输出: outline=[
  {title: "引言", summary: "AI 发展背景"},
  {title: "技术突破", summary: "大模型、多模态等"},
  {title: "应用场景", summary: "各行业落地案例"},
  {title: "未来展望", summary: "发展趋势预测"}
]
  ↓
outline_confirmation: HITL 中断（等待用户确认）
  ↓
用户确认: confirm_outline
  ↓
fan_out_writers: 并发启动 4 个 WriterNode
  ├─ writer_0: 撰写"引言" → sections[0]
  ├─ writer_1: 撰写"技术突破" → sections[1]
  ├─ writer_2: 撰写"应用场景" → sections[2]
  └─ writer_3: 撰写"未来展望" → sections[3]
  ↓
reducer_node: 合并 4 个章节，添加过渡段落
  ↓
输出: final_draft="# AI 发展趋势\n\n## 引言\n..."
```

### 修改大纲流程

```
输入: topic="Python 最佳实践"
  ↓
planner_node: 生成大纲（5 个章节）
  ↓
outline_confirmation: 中断
  ↓
用户修改: update_outline（调整为 3 个章节）
  ↓
graph.aupdate_state(config, {"outline": new_outline})
  ↓
resume_task: 恢复执行
  ↓
fan_out_writers: 并发启动 3 个 WriterNode
  ↓
reducer_node: 合并 3 个章节
  ↓
输出: final_draft
```

### 错误处理流程

```
输入: topic="..."
  ↓
planner_node: LLM 调用失败
  ↓
输出: error="大纲生成失败: ..."
  ↓
_route_after_planner: 检测到 error
  ↓
END: 流程结束（任务状态为 failed）
```

---

## 存储说明

| 数据 | 存储位置 | 说明 |
|------|----------|------|
| 任务元数据 | SQLite `tasks` 表 | 包含 task_id, status, topic, description |
| 最终结果 | SQLite `tasks.result` 字段 | final_draft 内容 |
| 大纲数据 | Checkpoint（不持久化到 SQLite） | 中断时保留，完成后清理 |
| 章节内容 | Checkpoint（不持久化到 SQLite） | 并发撰写时的中间状态 |

### 生命周期

```
任务创建 → _tasks dict (running) + Checkpoint
  ↓
大纲生成 → Checkpoint 保存大纲
  ↓
用户确认 → Checkpoint 保留（等待恢复）
  ↓
章节撰写 → Checkpoint 保存章节
  ↓
合并完成 → SQLite (completed) + Checkpoint 清理 + _tasks dict 移除
```

---

## 前端交互

### 任务创建

1. 用户输入主题和描述
2. 前端发送 `create_creation` WebSocket 消息
3. 后端启动任务，返回 `task_id` 和 `status: "interrupted"`
4. 前端跳转到任务详情页

### 大纲确认

1. 前端轮询或接收 WebSocket 推送，获取大纲内容
2. 用户查看大纲，可选择：
   - **确认**：发送 `resume_task` 消息（action: "confirm_outline"）
   - **修改**：编辑大纲后发送 `resume_task` 消息（action: "update_outline"，data: {outline: [...]}）

### 进度展示

| 节点 | 标签 | 进度 |
|------|------|------|
| `planner` | 生成大纲 | 20% |
| `outline_confirmation` | 大纲确认 | 30% |
| `writer` | 撰写章节 | 60% |
| `reducer` | 合并润色 | 90% |
| 完成 | - | 100% |

### 结果展示

- 展示 `final_draft` 内容
- 提供复制全文功能
- 支持 Markdown 渲染

---

## 技术细节

### Send API 实现

```python
# 扇出函数
def _fan_out_writers(state: CreationState) -> list[Send]:
    outline = state.get("outline", [])
    sends = []
    for i in range(len(outline)):
        writer_state = {...}
        sends.append(Send("writer", writer_state))
    return sends

# 注册条件边
graph.add_conditional_edges(
    "outline_confirmation",
    _fan_out_writers,  # 返回 list[Send]
)
```

### operator.add Reducer

```python
class CreationState(TypedDict):
    sections: Annotated[list[SectionContent], operator.add]
    messages: Annotated[list[BaseMessage], operator.add]
```

当多个 WriterNode 并行执行时，各自返回的 `sections` 列表会通过 `operator.add` 自动合并。

### Checkpoint 恢复

```python
# 中断时：Checkpoint 自动保存图状态
result = await graph.ainvoke(initial_state, config)  # 抛出 GraphInterrupt

# 恢复时：从 Checkpoint 读取状态，继续执行
result = await graph.ainvoke(Command(resume=True), config)
```

---

## 与 Polishing Graph 的关系

Creation Graph 和 Polishing Graph 是两个独立的图，但可以协同工作：

```
Creation Graph                    Polishing Graph
     │                                 │
     ▼                                 ▼
  创作文章                          润色文章
     │                                 │
     └──────────→ 作为输入 ──────────→┘
                  (content)
```

- Creation Graph 的输出（`final_draft`）可以作为 Polishing Graph 的输入（`content`）
- 用户可以在创作完成后选择润色模式进行二次优化
