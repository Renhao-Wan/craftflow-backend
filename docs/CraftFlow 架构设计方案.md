# CraftFlow AI —— 智能长文织造与多阶审校平台 架构设计方案

[[CraftFlow 设计补充文档]]  [[CraftFlow 工具调用]]  [[CraftFlow 接口流程图解]]  [[CraftFlow 核心开发蓝图与架构规范]]

## 1. 项目概述与设计哲学

### 1.1 痛点分析

当前业界主流的 LLM 应用（如直接调用豆包、ChatGPT 的基础对话）在处理“高质量长文生成”与“深度内容审校”时存在致命瓶颈：

* **上下文衰减与质量失控**：单次请求生成超长文本会导致细节丢失与严重的逻辑“幻觉”。
* **缺乏过程控制**：纯黑盒生成，用户无法干预中间状态（如大纲规划），不满意只能全部推翻重来。
* **事实准确性差**：纯文本生成的文章缺乏外部数据支撑，无法确保代码、技术事实的正确性。

---

### 1.2 核心设计理念

CraftFlow 定位为 **“虚拟编辑部”**，摒弃了“单次 Prompt 线性生成”的玩具模式，拥抱 **Agentic Workflow（智能体工作流）**。

系统依托 **LangGraph** 实现底层状态机，采用 **微服务架构 (FastAPI)** 将复杂的 AI 算力封装为标准化接口。核心设计遵循以下原则：

* **解耦的双轨流**：将“从 0 到 1 的创作”与“已有文章的润色”拆分为两个完全独立的状态机图，高内聚低耦合。
* **渐进式织造 (Map-Reduce)**：首创“大纲先行 + 并发撰写”机制，突破大模型长度限制。
* **强制人机协同 (HITL)**：在创作与审校的关键分岔路口，状态机主动挂起，将决策权交还给人类。

---

## 2. 系统总体架构

系统采用分层微服务架构，对外提供标准化 OpenAPI 供前端 Vue 或异构 Java 后端（如 KiwiHub）调用。

* **网关与路由层 (FastAPI)**：接收 RESTful 请求，进行入参校验，负责将外部请求映射为对底层特定 LangGraph 实例的触发与状态轮询。
* **AI 编排引擎层 (LangGraph)**：
  * **Creation Graph (渐进创作引擎)**：基于 `Send` 原语实现章节并发生成。
  * **Polishing Graph (多阶润色引擎)**：基于条件边 (`Conditional Edges`) 实现路由流转与多智能体博弈。
* **状态持久化层 (PostgreSQL/Redis)**：
  * 利用 LangGraph 的 `PostgresSaver` 作为图的持久化断点存储 (Checkpointer)。开发时使用 `MemorySaver`
  * Redis 用于外部系统的任务防重、限流及基础会话缓存。
* **工具链层 (LangChain Tools)**：集成 Google Search、Python REPL 安全沙箱等，用于执行硬核核查。

---

## 3. 核心工作流详细设计 (DAG 图设计)

### 3.1 渐进式创作流 (Creation Graph) —— Map-Reduce 架构

专精于长文的“骨肉分离”与“组装”。

**状态定义 (State Dict)**：
`topic` (主题) | `outline` (大纲) | `sections` (分片章节数组) | `draft` (组合草稿)

**节点流转逻辑 (Nodes & Edges)**：
1. **生成大纲** `PlannerNode`：接收 `topic`（主题） 和 `description`（用户描述），生成包含多节点的结构化大纲 `outline`。
2. **断点 1：大纲确认** `interrupt_before` 触发图挂起。前端展示大纲，用户拖拽修改后，通过 `Command(resume=...)` 重新注水图状态并唤醒。
3. **并发分发** `Map_Edge`：读取大纲，使用 LangGraph 的 `Send` API 将任务 Fan-out（扇出）给 $N$ 个并行线程。
4. **独立创作** `WriterNode` (并发)：$N$ 个智能体各自带着大纲的整体上下文，独立撰写自己的分块章节。
5. **草稿组装** `ReducerNode`：Fan-in（扇入）汇聚所有章节，进行上下文平滑过渡，生成完整 `draft`。ReducerNode 不应该一次性重写全文，而应该只是做“机械拼接”（Markdown 的 join），然后只针对章节与章节之间的过渡段落调用大模型进行微调润色。
6. **断点 2：定稿或转润色** 再次触发 `interrupt`，用户审阅草稿。若点击“完成”，图结束；若点击“进入润色”，前端调用 `/polishing` 接口将草稿移交下一管线。

### 3.2 多阶润色流 (Polishing Graph) —— 动态路由与多智能体对抗

针对不同 SLA 要求，提供弹性算力分级。

**状态定义 (State Dict)**：
`content` (当前内容) | `mode` (1/2/3 档) | `feedback` (改进建议) | `iteration` (迭代次数)

**节点流转逻辑 (Nodes & Edges)**：
1. **动态路由** `RouterNode`：根据外部传入的 `mode` 参数决定条件边 (Conditional Edges) 走向。
2. **一档：极速格式化** (Mode 1)：单次 LLM 调用，纠正错别字、排版，耗时最低，直接输出定稿。
3. **二档：专家对抗循环** (Mode 2)：进入 **Debate Loop**。
   * `AuthorNode`：根据提示重写内容。
   * `EditorNode`：扮演主编角色进行多维度打分评估（如连贯性、深度）。
   * *条件判断*：若主编打分 $\ge 90$ 或迭代达到 3 次 $\to$ 结束输出；否则带着主编的毒舌反馈流回 `AuthorNode`。
1. **三档：硬核事实核查** (Mode 3)：包含 Mode 2 的所有逻辑，但在其前方插入 `FactCheckerNode`。
   * `FactChecker` 自动剥离文章中的声明、代码，调用外部工具。生成“防幻觉侦查报告”，强制 `AuthorNode` 必须修复这些硬伤。

---

## 4. API 矩阵与异构集成设计

为彻底解决大模型长周期推理带来的 HTTP Timeout 问题，并实现与 KiwiHub (Java 生态) 的完美解耦，系统采用 **Async Request-Reply (异步提交 + 状态轮询)** 模式。

### 4.1 核心 RESTful API 规范

* **POST /api/v1/creation** (创建写作任务)
  * 请求：`{"topic": "微服务架构演进", "hitl_enabled": true}`
  * 响应：`{"task_id": "c-UUID", "status": "running"}` *(迅速返回，不阻塞)*
* **GET /api/v1/tasks/{task_id}** (状态轮询)
  * 请求参数：轮询图状态。
  * 响应示例 1 (执行中)：`{"status": "running", "current_node": "WriterNode"}`
  * 响应示例 2 (遇断点挂起)：`{"status": "interrupted", "awaiting": "outline_confirmation", "data": {...大纲内容...}}`
* **POST /api/v1/tasks/{task_id}/resume** (人机协同注入点)
  * 请求：`{"action": "confirm_outline", "modified_data": {...修改后的大纲...}}`
  * 行为：引擎拉取 PostgreSQL 中的图快照，注入新数据继续运行。
* **POST /api/v1/polishing** (发起润色任务)
  * 请求：`{"content": "正文...", "mode": 3}`
  * 响应：`{"task_id": "p-UUID", "status": "running"}`

### 4.2 KiwiHub (Java 端) 协同架构

Java 后端完全不需要知道内部图逻辑。当社区用户需要“AI 扩写帖子”时：

1. KiwiHub 组装 JSON 调用 FastAPI `POST /creation`。
2. KiwiHub 拿到 `task_id` 后，通过异步线程/定时任务定期 `GET /tasks/{task_id}`。
3. 当 CraftFlow 处于 `interrupted` 时，Java 通过 WebSocket 通知终端用户弹出确认面板。
4. 完成后，Java 拉取最终 Markdown 数据存入 MySQL/MongoDB 主库。

---

## 5. 项目核心技术壁垒与亮点总结

在简历答辩或技术方案评审时，重点突出以下四大降维打击能力：

1. **复杂并发控制图谱 (Map-Reduce on DAG)**
   不仅掌握大模型单次请求，更成功利用 LangGraph 的 `Send` API 在创作流中实现了子任务的大规模扇出与扇入。从底层解决了大语言模型处理十万字长文本的上下文遗忘瓶颈。
2. **长周期有状态任务调度 (Stateful AI Service)**
   成功将原本“无状态”的 FastAPI 服务，借助 Checkpointer 升级为“有持久化状态”的工作流引擎。支持长达数小时的任务任意挂起 (`interrupt`)、前端干预与安全重入 (`resume`)。
3. **弹性算力与动态路由 (Dynamic Routing in Polishing)**
   设计三阶润色模式，将策略模式（Strategy Pattern）与图的条件边完美融合。高阶模式融合 Debate（多智能体博弈）与 Tool Use（外挂验证），展现了极强的架构控制力与质量兜底能力。
4. **跨语言异构系统的平滑解耦**
   没有将 Agent 代码与原业务逻辑揉在一起，而是抽象为标准 SaaS 服务。利用轮询机制解决长时异步调度痛点，体现了扎实的微服务架构师视野。
