# CraftFlow —— 核心开发蓝图与架构规范

## 1. 项目概述与定位

**CraftFlow** 是一个基于 Agentic Workflow 的智能长文织造与多阶审校平台。系统采用分层微服务架构，对外提供异步 API，底层由 LangGraph 驱动双轨状态机。

本项目的核心工程挑战与架构特色在于：

1. **彻底解耦的双图架构**：将创作 (`Creation Graph`) 与润色 (`Polishing Graph`) 物理分离，通过前端与 FastAPI 路由连接，避免单一巨型图的状态污染。
2. **渐进式织造 (Map-Reduce)**：在创作图中，摒弃大模型单次线性生成。先生成大纲 $\to$ **触发人工断点 (HITL) 修改大纲** $\to$ 利用 LangGraph `Send` API 并发拉起多个 Agent 分别撰写章节 $\to$ 最终组装。
3. **弹性多阶审校与子图复用**：在润色图中，根据 `mode` 参数实现动态路由。高级别润色会复用**多智能体对抗子图 (Debate Subgraph)**，并触发外挂工具链进行严格的事实核查。
4. **长周期有状态任务**：通过 `Checkpointer` (开发期 `MemorySaver`，生产期 `PostgresSaver`) 持久化状态，采用异步提交 + 轮询机制，解决 HTTP 接口超时瓶颈。

## 2. 核心技术栈规范

* **后端框架**: Python 3.11+, FastAPI, Pydantic
* **AI 编排**: LangGraph (核心状态机编排), LangChain (工具与模型抽象)
* **持久化**: `PostgresSaver` (LangGraph 原生 Checkpointer，前期开发可先用 `MemorySaver` 占位), PostgreSQL (pgvector 可选，用于 RAG)
* **中间件**: Redis (用于限流、防并发去重)
* **LLM**: 可配置的基座模型，所有模型同一使用 OpenAI，通过 LangChain 统一封装.从环境变量文件中加载（如：.env）

  ```yaml
    # 默认配置
	LLM_API_KEY="sk-your-openai-api-key-here"
    LLM_API_BASE=""
    LLM_MODEL="gpt-4-turbo"
    MAX_TOKENS=4096

    # LLM 差异参数
    DEFAULT_TEMPERATURE=0.7
    EDITOR_NODE_TEMPERATURE=0.2    # 主编打分需要低随机性
  ```

## 3. 核心图谱设计与状态定义 (Graph & State)

*(注：请在开发时严格遵循以下状态字典的定义，确保强类型与无状态副作用)*

### 3.1 渐进式创作流 (Creation Graph)

* **职责**：
* **状态定义 (`CreationState` TypedDict)**:
  * `topic`: str (用户输入的主题)
  * `description`: str (补充描述/需求)
  * `outline`: list[dict] (大纲结构，必须包含章节名与概要)
  * `sections`: list[str] (通过 Reducer `operator.add` 聚合的并发章节)
  * `draft`: str (最终组合出的 Markdown 草稿)
* **节点流转**:
  `PlannerNode` $\to$ **`interrupt_before` (挂起等待大纲确认)** $\to$ `MapEdge` (基于 `Send` API 并发拉起 Writer) $\to$ 并发执行 `WriterNode` $\to$ `ReducerNode` (机械拼装与过渡段润色) $\to$ END。

### 3.2 专家对抗子图 (Debate Subgraph)

* **职责**：高内聚的组件图，专用于“作者写 $\to$ 主编骂 $\to$ 作者改”的闭环。
* **状态定义 (`DebateState` TypedDict)**:
  * `content`: str (当前正在打磨的文本)
  * `feedback`: str (主编给出的修改建议)
  * `iteration`: int (循环计数器)
  * `score`: int (打分 0-100)
* **节点流转**:
  `AuthorNode` $\to$ `EditorNode` $\to$ `Conditional Edge` (若 `score` $\ge 90$ 或 `iteration` $\ge 3$ 则结束，否则流回 `AuthorNode`)。

### 3.3 多阶润色流 (Polishing Graph)

* **职责**：接收现有草稿，基于模式动态路由算力。
* **状态定义 (`PolishingState` TypedDict)**:
  * `content`: str (草稿及润色后的正文)
  * `mode`: int (1: 极速, 2: 专家对抗, 3: 事实核查)
* **节点流转**:
  `RouterNode` (条件路由)
  * $\to$ **Mode 1**: `FormatterNode` $\to$ END
  * $\to$ **Mode 2**: 直接调用 `Debate Subgraph` $\to$ END
  * $\to$ **Mode 3**: `FactCheckerNode` (外挂查证) $\to$ `AuthorNode` (强制事实修复) $\to$ 调用 `Debate Subgraph` $\to$ END

### 3.1 Creation Graph (渐进式创作流)

**职责**：接收主题 -> 生成大纲 -> 挂起等待人类修改 -> 并发写章节 -> 汇总拼装 -> 图结束。

* **状态定义 (`CreationState` TypedDict)**:
  * `topic`: str (用户输入的主题)
  * `outline`: list[dict] (大纲结构，包含章节标题与概要)
  * `sections`: list[str] (各章节生成的内容，需配合 Reducer 聚合)
  * `draft`: str (最终合并的 Markdown 草稿)
* **核心节点与流转**:
  1. `PlannerNode`: 根据 `topic` 生成 `outline`。
  2. `interrupt_before`: 设置在 `MapEdge` 之前，强制挂起，等待前端修改 `outline` 并恢复。
  3. `MapEdge` (条件边/Send API): 遍历 `outline`，为每个章节 Fan-out 到 `WriterNode`。
  4. `WriterNode`: 并发节点，生成单章内容并写入 `sections`。
  5. `ReducerNode`: Fan-in 节点，将 `sections` 机械合并，并调用 LLM 润色过渡段，输出 `draft`。

### 3.2 Debate Subgraph (多智能体对抗子图)

**职责**：一个独立的微型状态机，专用于“作者重写 - 主编打分”的闭环，供 Polishing Graph 内部复用。
* **状态定义 (`DebateState` TypedDict)**:
  * `content`: str (当前文本)
  * `feedback`: str (主编给出的修改意见)
  * `iteration`: int (循环次数，每次经过 Editor 递增)
  * `score`: int (打分 0-100)
* **节点流转**:
  `AuthorNode` (重写) -> `EditorNode` (打分/提意见) -> 判定 (score>=90 或 iter>=3 则返回，否则回到 AuthorNode)

### 3.3 Polishing Graph (多阶润色流主图)

**职责**：将一句话需求通过 `Map-Reduce` 并发转化为长文草稿。执行完毕后即结束，不包含润色逻辑。
* **状态定义 (`PolishingState` TypedDict)**:
  * `content`: str (初始草稿及最终内容)
  * `mode`: int (1: 极速格式化, 2: 对抗审查, 3: 事实核查)
  * `fact_report`: str (事实核查报告，仅 Mode 3 用)
* **核心流转**:
  1. `RouterNode`: 根据 `mode` 决定边走向。
  2. **Mode 1 边**: 走向 `FormatterNode` (单次 Prompt 润色) -> END。
  3. **Mode 2 边**: 走向 `Debate Subgraph` 组件 -> END。
  4. **Mode 3 边**: 走向 `FactCheckerNode` (调用搜索/沙箱生成 `fact_report`) -> `FixFactNode` (强制融合报告) -> 走向 `Debate Subgraph` 组件 -> END。

## 4. 贯穿全生命周期的工具链 (Tool Bindings)

必须利用 `llm.bind_tools()` 机制将以下工具绑定到对应节点的 Agent 上，严禁纯黑盒生成：

| 触发节点 | 绑定工具集 (app/graph/tools/) | 核心作用说明 |
| :--- | :--- | :--- |
| **PlannerNode** | `TavilySearch`, `LocalKnowledge_Retriever` | 搜索前沿行业动态或查阅本地知识库 (向量检索)，确保大纲具备深度专业视角。 |
| **WriterNode** | `WebScraper` | 解析 URL 获取长文正文，辅助深度章节的资料提炼，防止仅靠摘要导致的幻觉。 |
| **FactChecker** | `E2B_CodeInterpreter`, `TavilySearch`, `LinkValidator` | **核心质量墙**。通过沙箱运行代码片段捕获报错、通过全网交叉对比实体数据、利用 Python 脚本校验 Markdown 死链，生成《防幻觉侦查报告》。 |
| **EditorNode** | `Calculate_Readability` | 无需 LLM 算力，纯 Python 计算文章的 Flesch-Kincaid 可读性分数、词汇丰度，量化打分依据。 |

## 5. 核心 API 契约 (FastAPI)

对外暴露基于 Async Request-Reply 模式的接口，实现与异构业务系统解耦。

* **POST `/api/v1/creation`**
  * 入参: `{"topic": "...", "requirements": "..."}`
  * 出参: `{"task_id": "c-UUID", "status": "running"}`
* **POST `/api/v1/polishing`**
  * 入参: `{"content": "...", "mode": 3}`
  * 出参: `{"task_id": "p-UUID", "status": "running"}`
* **GET `/api/v1/tasks/{task_id}`**
  * 出参:
	* 状态 1 (运行中): `{"status": "running", "state": {...}}`
	* 状态 2 (遇断点): `{"status": "interrupted", "awaiting": "human_outline_edit", "data": {"outline": [...]}}`
	* 状态 3 (完成): `{"status": "completed", "result": "..."}`
* **POST `/api/v1/tasks/{task_id}/resume`**
  * 入参: `{"action": "update_outline", "data": {"outline": [...]}}`
  * 逻辑: 调用 `graph.invoke(Command(resume=data), config={"configurable": {"thread_id": task_id}})` 唤醒图。

## 6. 工程目录结构

```text
craftflow-backend/
├── app/
│   ├── api/                     # Controller 层 (路由与依赖注入)
│   │   ├── dependencies.py      # FastAPI 依赖 (DB Session, Graph 实例获取)
│   │   └── v1/
│   │       ├── router.py        # API 路由总线聚合
│   │       ├── creation.py      # /api/v1/creation 接口集
│   │       └── polishing.py     # /api/v1/polishing 接口集
│   ├── core/                    # 基础设施层
│   │   ├── config.py            # 全局配置 (Pydantic BaseSettings 读取 .env)
│   │   ├── exceptions.py        # 全局异常捕获与自定义异常
│   │   └── logger.py            # 日志配置 (Loguru)
│   ├── graph/                   # ★ LangGraph 核心编排引擎层
│   │   ├── common/              # 共享抽象 (通用状态类、基础 Agent Prompt)
│   │   ├── tools/               # 外部工具链封装
│   │   │   ├── search.py        # TavilySearch 封装
│   │   │   ├── sandbox.py       # E2B_CodeInterpreter 沙箱封装
│   │   │   └── validators.py    # 死链校验、可读性评估等纯函数工具
│   │   ├── creation/            # Creation Graph 模块
│   │   │   ├── state.py         # CreationState 定义
│   │   │   ├── nodes.py         # Planner, Writer, Reducer 节点具体实现
│   │   │   └── builder.py       # 构建与编译 Creation 图
│   │   └── polishing/           # Polishing Graph 模块
│   │       ├── state.py         # PolishingState 定义
│   │       ├── nodes.py         # Router, Formatter, FactChecker 节点实现
│   │       ├── debate_graph.py  # 独立的 Debate Subgraph 组件编译
│   │       └── builder.py       # 构建与编译 Polishing 主图
│   ├── schemas/                 # Pydantic 数据校验模型 (DTO)
│   │   ├── request.py           # API 入参模型
│   │   └── response.py          # API 响应模型
│   ├── services/                # Service 层 (桥接 API 与 Graph)
│   │   ├── checkpointer.py      # PostgresSaver/MemorySaver 实例管理中心
│   │   ├── creation_svc.py      # 封装发起创作、挂起唤醒的具体业务逻辑
│   │   └── polishing_svc.py     # 封装发起润色的具体业务逻辑
│   └── main.py                  # FastAPI 应用入口、中间件挂载、生命周期管理
├── tests/                       # 测试目录
│   ├── conftest.py              # Pytest 夹具 (Fixtures)
│   ├── test_api/                # 接口端到端测试
│   └── test_graph/              # 图流转单元测试
├── logs/                        # 运行时日志持久化目录
├── docs/                        # 开发文档/展示文档
├── .env                         # 本地环境配置 (生产/默认环境变量)
├── .env.dev                     # 本地环境配置 (开发/调试专属)
├── .env.example                 # 环境配置模板 (供协作者参考，脱敏)
├── .gitignore                   # Git 忽略规则 (忽略 .env, logs, __pycache__ 等)
├── langgraph.json               # LangGraph Studio 专属调试配置
├── pyproject.toml               # 环境依赖 (langchain, fastapi 等)
└── README.md                    # 项目核心介绍文档
```
