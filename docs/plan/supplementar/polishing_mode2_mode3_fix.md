# 润色模式2/模式3 问题分析与修复方案

**文档类型**: 补充设计文档
**创建日期**: 2026-05-07
**关联模块**: `app/graph/polishing/`

---

## 一、问题发现

在端到端测试中发现三个润色模式的输出与输入几乎相同，进一步分析日志后定位到模式2和模式3存在设计实现层面的问题。

---

## 二、模式2（深度润色）问题分析

### 2.1 设计初衷

Author-Editor 博弈循环：Editor 严格打分，Author 根据反馈反复重写，直到达到 90 分或迭代 3 轮。

### 2.2 实际表现

对抗循环一轮即结束，输出与输入几乎无差异。

### 2.3 根因分析

| # | 问题 | 根因 | 位置 |
|---|------|------|------|
| 2-1 | Editor 评分虚高，首轮就给 90+ 分 | Editor prompt 没有"严格打分"指导，LLM 倾向于给高分（四个维度各25分，容易给20+） | `debate/prompts.py` EDITOR_SYSTEM_PROMPT |
| 2-2 | Author 首轮没有真实反馈 | 首轮 `editor_feedback` 为空时用"这是第一轮润色，请对文章进行全面优化"替代，指令过于模糊 | `debate/nodes.py` author_node |
| 2-3 | Author prompt 太温和 + 防幻觉约束导致保守修改 | prompt 要求"语言优化、逻辑优化"但没有要求"显著改进"；`include_anti_hallucination=True` 让 LLM 不敢大改 | `debate/prompts.py` AUTHOR_SYSTEM_PROMPT |

### 2.4 数据流（修复前）

```
START → author(第1轮, 无反馈, 自由润色) → editor(给94分) → increment(1)
→ should_continue(94>=90, 结束) → finalize(author_output=第1轮输出) → END
```

---

## 三、模式3（事实核查）问题分析

### 3.1 设计初衷

核查文章中的事实性内容，使用搜索工具验证关键事实，输出修正后的文章。

### 3.2 实际表现

输出是一份 JSON 格式的核查报告（约500字），而非修正后的文章。搜索工具从未被实际执行。

### 3.3 根因分析

| # | 问题 | 根因 | 位置 |
|---|------|------|------|
| 3-1 | 搜索工具从未执行 | `llm.bind_tools(SEARCH_TOOLS)` 只把工具描述发给 LLM，不等于"执行工具"。需要 agent loop 处理 `response.tool_calls` | `nodes.py` fact_checker_node |
| 3-2 | 输出是 JSON 报告，不是修正后的文章 | prompt 要求输出 `overall_accuracy`、`issues` 等 JSON 字段；`_extract_result` 直接返回 `fact_check_result` | `prompts.py` FACT_CHECKER_SYSTEM_PROMPT |
| 3-3 | 核查完直接结束，不进入修正流程 | 图结构 `fact_checker → END`，没有条件边串联 debate | `builder.py` |
| 3-4 | State 中 fact_checker 不设置 `final_content` | 只设 `fact_check_result`，`_extract_result` 走 fallback | `nodes.py` fact_checker_node |

### 3.4 bind_tools vs agent loop 的区别

```python
# 当前实现（错误）：bind_tools 只发工具描述，不执行
llm_with_tools = llm.bind_tools(SEARCH_TOOLS)
response = await llm_with_tools.ainvoke(messages)
# response.tool_calls 可能包含调用请求，但代码从未处理

# 正确实现：agent loop
response = await llm_with_tools.ainvoke(messages)
while response.tool_calls:
    messages.append(response)
    for tc in response.tool_calls:
        result = tool_map[tc["name"]].invoke(tc["args"])
        messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
    response = await llm_with_tools.ainvoke(messages)
```

### 3.5 数据流（修复前）

```
START → router(mode=3) → fact_checker(LLM 单次调用, bind_tools 无实际执行)
→ 返回 JSON 报告 → _extract_result 读 fact_check_result → END
```

---

## 四、修复方案

### 4.1 模式2 修复

#### 4.1.1 Editor 严格评分

修改 `debate/prompts.py` 中 `EDITOR_SYSTEM_PROMPT`：

- 加入"严格压分"核心原则：大多数文章首轮评分应在 55-75 之间
- 明确约束：**首轮总分不得超过 80 分**
- 每个维度增加具体扣分标准
- 加入评分纪律：每轮至少列出 3 条改进建议，上一轮的改进要求下一轮必须逐条检查

#### 4.1.2 Author prompt 强化

修改 `debate/prompts.py` 中 `AUTHOR_SYSTEM_PROMPT`：

- 任务从"重写与润色"升级为"深度重写"
- 加入核心原则："大胆改动"、"重写而非修补"、"增强说服力"、"提升可读性"
- 去掉 `include_anti_hallucination=True`（模式2不涉及事实核查，防幻觉约束会限制改动幅度）
- 新增"事实核查上下文处理"段落，为模式3串联做准备

#### 4.1.3 Author node 首轮反馈

修改 `debate/nodes.py` 中 `author_node`：

- 首轮 `editor_feedback` 为空时，不再使用模糊的"请全面优化"，改为具体的四点改进方向
- 新增 `fact_check_result` 参数传递

### 4.2 模式3 修复

#### 4.2.1 实现 agent loop

修改 `nodes.py` 中 `fact_checker_node`：

- 在 LLM 调用后检查 `response.tool_calls`
- 如果有工具调用，执行搜索工具并将结果作为 `ToolMessage` 喂回 LLM
- 最多循环 `MAX_TOOL_ROUNDS = 3` 次
- 使用 `tool_map = {t.name: t for t in SEARCH_TOOLS}` 映射工具名到工具实例

#### 4.2.2 核查后串联修正

修改图结构（`builder.py`）：

```
修复前：fact_checker → END
修复后：fact_checker → route_after_fact_check
                        ├─ "debate" → debate_node → END  （有问题）
                        └─ "end" → END                   （无问题）
```

修改 `nodes.py`：新增 `route_after_fact_check` 条件边函数，根据 `needs_revision` 标记决定路由。

#### 4.2.3 State 新增字段

- `PolishingState` 新增 `needs_revision: bool` —— 标记核查是否发现问题
- `DebateState` 新增 `fact_check_result: Optional[str]` —— 传递核查报告给 Author

#### 4.2.4 debate_node 接收核查结果

修改 `builder.py` 中 `debate_node`：

- 从 `state` 读取 `fact_check_result`
- 传递给 `DebateState` 的 `fact_check_result` 字段
- Author node 根据此字段在 prompt 中加入核查上下文

---

## 五、修复后的数据流

### 模式2

```
START → author(第1轮, 有具体改进方向) → editor(严格打分, 给68分)
→ increment(1) → should_continue(68<90, 继续)
→ author(第2轮, 根据editor反馈改进) → editor(给82分)
→ increment(2) → should_continue(82<90, 继续)
→ author(第3轮) → editor(给91分)
→ increment(3) → should_continue(91>=90 或 3>=3, 结束)
→ finalize(author_output=第3轮输出) → END
```

### 模式3（有问题）

```
START → router(mode=3) → fact_checker(agent loop: LLM → 搜索工具 → LLM)
→ route_after_fact_check(needs_revision=True)
→ debate(基于核查报告修正文章) → END
```

### 模式3（无问题）

```
START → router(mode=3) → fact_checker(agent loop: LLM → 搜索工具 → LLM)
→ route_after_fact_check(needs_revision=False)
→ END（原文返回）
```

---

## 六、变更文件清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/graph/polishing/debate/prompts.py` | 修改 | Editor 严格评分 prompt、Author 强化 prompt、新增 fact_check_context |
| `app/graph/polishing/debate/nodes.py` | 修改 | Author node 首轮反馈、传递 fact_check_result |
| `app/graph/polishing/debate/state.py` | 修改 | DebateState 新增 fact_check_result 字段 |
| `app/graph/polishing/nodes.py` | 修改 | fact_checker agent loop、route_after_fact_check |
| `app/graph/polishing/state.py` | 修改 | PolishingState 新增 needs_revision 字段 |
| `app/graph/polishing/builder.py` | 修改 | 条件边串联、debate_node 传递核查结果 |
| `app/services/polishing_svc.py` | 修改 | initial_state 新增 needs_revision |
| `tests/test_graph/test_polishing_state.py` | 修改 | 同步 State 字段 |
| `tests/test_graph/test_polishing_nodes.py` | 修改 | 同步 State 字段 |
| `tests/test_graph/test_polishing_graph.py` | 修改 | 同步 State 字段、新增 Mode 3 条件边测试 |
| `tests/test_graph/test_debate_graph.py` | 修改 | 同步 State 字段 |
