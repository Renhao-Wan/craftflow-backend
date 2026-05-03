# CraftFlow Backend 开发计划

> 本文档基于 CraftFlow 架构设计方案，提供逐文件实现的详细开发路线图。

## 一、项目文件清单与职责说明

### 1. 根目录配置文件

| 文件路径             | 职责描述                                       | 依赖模块 |
|------------------|--------------------------------------------|------|
| `.env.example`   | 环境变量模板（脱敏），供协作者参考                          | 无    |
| `.env.dev`       | 开发环境配置（LLM API Key、数据库连接等）                 | 无    |
| `.gitignore`     | Git 忽略规则（.env, logs, __pycache__, .venv 等） | 无    |
| `pyproject.toml` | 项目依赖管理（Poetry/pip），定义 Python 版本、核心库版本      | 无    |
| `langgraph.json` | LangGraph Studio 调试配置                      | 无    |
| `README.md`      | 项目核心介绍、快速启动指南                              | 无    |

### 2. app/core/ - 基础设施层

| 文件路径                     | 职责描述                                                                   | 依赖模块                |
|--------------------------|------------------------------------------------------------------------|---------------------|
| `app/core/__init__.py`   | 包标识文件                                                                  | 无                   |
| `app/core/config.py`     | 全局配置类（Pydantic BaseSettings），从 .env 读取环境变量（LLM Provider、数据库 URL、日志级别等） | `pydantic-settings` |
| `app/core/exceptions.py` | 自定义异常类（GraphExecutionError、CheckpointerError 等）与全局异常处理器                | `fastapi`           |
| `app/core/logger.py`     | 结构化日志配置（使用 loguru）                                                     | `loguru`            |

### 3. app/schemas/ - 数据传输对象 (DTO)

| 文件路径                      | 职责描述                                                       | 依赖模块       |
|---------------------------|------------------------------------------------------------|------------|
| `app/schemas/__init__.py` | 包标识文件                                                      | 无          |
| `app/schemas/request.py`  | API 请求模型（CreationRequest, PolishingRequest, ResumeRequest） | `pydantic` |
| `app/schemas/response.py` | API 响应模型（TaskResponse, TaskStatusResponse, ErrorResponse）  | `pydantic` |

### 4. app/graph/common/ - 共享抽象层

| 文件路径                              | 职责描述                                            | 依赖模块                |
|-----------------------------------|-------------------------------------------------|---------------------|
| `app/graph/common/__init__.py`    | 包标识文件                                           | 无                   |
| `app/graph/common/llm_factory.py` | LLM 单例工厂（根据环境变量返回 OpenAI 实例） | `langchain-openai`  |
| `app/graph/common/prompts.py`     | **仅存放通用、跨模块可复用的 Prompt 模板**（如：通用输出格式、Markdown 规范等） | `langchain-core`    |

### 5. app/graph/tools/ - 外部工具链封装

| 文件路径                            | 职责描述                                | 依赖模块                                   |
|---------------------------------|-------------------------------------|----------------------------------------|
| `app/graph/tools/__init__.py`   | 包标识文件                               | 无                                      |
| `app/graph/tools/search.py`     | TavilySearch 工具封装（互联网搜索）            | `langchain-community`, `tavily-python` |
| `app/graph/tools/sandbox.py`    | E2B CodeInterpreter 沙箱封装（代码执行与验证）   | `e2b-code-interpreter`                 |
| `app/graph/tools/validators.py` | 纯 Python 工具（链接验证、可读性计算、Markdown 解析） | `requests`, `beautifulsoup4`           |
| `app/graph/tools/retriever.py`  | 本地知识库检索工具（对接 pgvector 或 Milvus）     | `langchain-postgres`, `langchain-core` |

### 6. app/graph/creation/ - Creation Graph 模块

| 文件路径                             | 职责描述                                                        | 依赖模块                                                    |
|----------------------------------|-------------------------------------------------------------|---------------------------------------------------------|
| `app/graph/creation/__init__.py` | 包标识文件                                                       | 无                                                       |
| `app/graph/creation/state.py`    | CreationState TypedDict 定义（topic, outline, sections, draft） | `typing`, `langgraph`                                   |
| `app/graph/creation/prompts.py`  | **Creation 专属 Prompt 模板**（PlannerNode、WriterNode、ReducerNode 的提示词） | `langchain-core`                                        |
| `app/graph/creation/nodes.py`    | 节点实现（PlannerNode, WriterNode, ReducerNode）                  | `langchain-core`, `app.graph.common`, `app.graph.tools`, `app.graph.creation.prompts` |
| `app/graph/creation/builder.py`  | 构建与编译 Creation Graph（定义边、interrupt 点）                       | `langgraph`, `app.graph.creation.nodes`                 |

### 7. app/graph/polishing/ - Polishing Graph 模块

| 文件路径                                  | 职责描述                                                                     | 依赖模块                                                    |
|---------------------------------------|--------------------------------------------------------------------------|---------------------------------------------------------|
| `app/graph/polishing/__init__.py`     | 包标识文件                                                                    | 无                                                       |
| `app/graph/polishing/state.py`        | PolishingState 与 DebateState TypedDict 定义                                | `typing`, `langgraph`                                   |
| `app/graph/polishing/prompts.py`      | **Polishing 专属 Prompt 模板**（RouterNode、FormatterNode、FactCheckerNode、AuthorNode、EditorNode 的提示词） | `langchain-core`                                        |
| `app/graph/polishing/nodes.py`        | 节点实现（RouterNode, FormatterNode, FactCheckerNode, AuthorNode, EditorNode） | `langchain-core`, `app.graph.common`, `app.graph.tools`, `app.graph.polishing.prompts` |
| `app/graph/polishing/debate_graph.py` | 独立的 Debate Subgraph 编译（Author-Editor 对抗循环）                               | `langgraph`, `app.graph.polishing.nodes`                |
| `app/graph/polishing/builder.py`      | 构建与编译 Polishing 主图（条件路由、子图调用）                                            | `langgraph`, `app.graph.polishing.debate_graph`         |

### 8. app/services/ - 业务服务层

| 文件路径                            | 职责描述                                                    | 依赖模块                                                       |
|---------------------------------|---------------------------------------------------------|------------------------------------------------------------|
| `app/services/__init__.py`      | 包标识文件                                                   | 无                                                          |
| `app/services/checkpointer.py`  | Checkpointer 单例管理（根据环境变量返回 MemorySaver 或 PostgresSaver） | `langgraph-checkpoint`, `langgraph-checkpoint-postgres`    |
| `app/services/creation_svc.py`  | Creation 业务逻辑封装（启动任务、处理 interrupt、恢复执行）                 | `app.graph.creation.builder`, `app.services.checkpointer`  |
| `app/services/polishing_svc.py` | Polishing 业务逻辑封装（启动任务、模式路由）                             | `app.graph.polishing.builder`, `app.services.checkpointer` |

### 9. app/api/ - Controller 层

| 文件路径                      | 职责描述                                                                    | 依赖模块                                                     |
|---------------------------|-------------------------------------------------------------------------|----------------------------------------------------------|
| `app/api/__init__.py`     | 包标识文件                                                                   | 无                                                        |
| `app/api/dependencies.py` | FastAPI 依赖注入（获取 Graph 实例、Checkpointer、日志器）                              | `fastapi`, `app.services`                                |
| `app/api/v1/__init__.py`  | 包标识文件                                                                   | 无                                                        |
| `app/api/v1/creation.py`  | Creation 相关路由（POST /creation, GET /tasks/{id}, POST /tasks/{id}/resume） | `fastapi`, `app.schemas`, `app.services.creation_svc`    |
| `app/api/v1/polishing.py` | Polishing 相关路由（POST /polishing）                                         | `fastapi`, `app.schemas`, `app.services.polishing_svc`   |
| `app/api/v1/router.py`    | 聚合 v1 版本所有路由                                                            | `fastapi`, `app.api.v1.creation`, `app.api.v1.polishing` |

### 10. app/main.py - 应用入口

| 文件路径          | 职责描述                                              | 依赖模块                                       |
|---------------|---------------------------------------------------|--------------------------------------------|
| `app/main.py` | FastAPI 应用实例化、中间件挂载、生命周期事件（startup/shutdown）、路由注册 | `fastapi`, `app.api.v1.router`, `app.core` |

### 11. tests/ - 测试模块

| 文件路径                                       | 职责描述                              | 依赖模块                            |
|--------------------------------------------|-----------------------------------|---------------------------------|
| `tests/__init__.py`                        | 包标识文件                             | 无                               |
| `tests/conftest.py`                        | Pytest 全局夹具（mock LLM、测试数据库、测试客户端） | `pytest`, `pytest-asyncio`      |
| `tests/test_api/__init__.py`               | 包标识文件                             | 无                               |
| `tests/test_api/test_creation.py`          | Creation API 端到端测试                | `httpx`, `pytest`               |
| `tests/test_api/test_polishing.py`         | Polishing API 端到端测试               | `httpx`, `pytest`               |
| `tests/test_graph/__init__.py`             | 包标识文件                             | 无                               |
| `tests/test_graph/test_creation_graph.py`  | Creation Graph 单元测试（节点逻辑、状态流转）    | `pytest`, `app.graph.creation`  |
| `tests/test_graph/test_polishing_graph.py` | Polishing Graph 单元测试              | `pytest`, `app.graph.polishing` |

---

## 二、分阶段开发任务 (Task Breakdown)

| Task ID     | 任务名称               | 完成状态 | 涉及文件                                                                                                                       | 实现要点                                                                                                                                                                  | 预估行数 | 核心依赖库                                                                 |
|-------------|--------------------|------|----------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|------|-----------------------------------------------------------------------|
| **Task 1**  | 项目初始化与配置           | 是    | `.gitignore`, `pyproject.toml`, `.env.example`, `.env.dev`, `README.md`, `langgraph.json`                                  | 1. 创建 Poetry/pip 项目结构<br>2. 定义核心依赖（fastapi, langgraph, langchain, pydantic）<br>3. 配置 .gitignore 忽略敏感文件<br>4. 创建所有目录结构和 __init__.py 文件                                 | 100  | `poetry`, `python-dotenv`                                             |
| **Task 2**  | 基础设施层实现            | 是    | `app/core/config.py`, `app/core/logger.py`, `app/core/exceptions.py`                                                       | 1. 使用 Pydantic BaseSettings 读取环境变量<br>2. 配置结构化日志（loguru）<br>3. 定义自定义异常类与 FastAPI 异常处理器                                                                                | 150  | `pydantic-settings`, `loguru`                                         |
| **Task 3**  | 数据模型定义             | 是    | `app/schemas/request.py`, `app/schemas/response.py`                                                                        | 1. 定义 CreationRequest（topic, description）<br>2. 定义 PolishingRequest（content, mode）<br>3. 定义 TaskResponse、TaskStatusResponse                                           | 120  | `pydantic`                                                            |
| **Task 4**  | LLM 工厂与通用 Prompt   | 是    | `app/graph/common/llm_factory.py`, `app/graph/common/prompts.py`                                                           | 1. 实现单例模式的 LLM 工厂（根据环境变量返回不同 Provider）<br>2. 定义**通用、跨模块可复用**的 Prompt 模板（如：Markdown 输出格式规范、通用角色定义等）                                                                                                                                     | 180  | `langchain-openai`, `langchain-anthropic`, `langchain-core`           |
| **Task 5**  | 工具链封装              | 是    | `app/graph/tools/search.py`, `app/graph/tools/sandbox.py`, `app/graph/tools/validators.py`, `app/graph/tools/retriever.py` | 1. 封装 TavilySearch 为 @tool<br>2. 封装 E2B CodeInterpreter（可选）<br>3. 实现链接验证、可读性计算工具<br>4. 实现本地知识库检索（PGVector + Chroma 自动降级）                                                                  | 250  | `tavily-python`, `e2b-code-interpreter`, `requests`, `beautifulsoup4`, `chromadb`, `langchain-chroma` |
| **Task 6**  | Creation State 定义  | 是    | `app/graph/creation/state.py`                                                                                              | 1. 定义 CreationState TypedDict<br>2. 配置 sections 字段的 Reducer（operator.add）                                                                                             | 50   | `typing`, `langgraph`                                                 |
| **Task 7**  | Creation Prompts 与节点实现      | 是    | `app/graph/creation/prompts.py`, `app/graph/creation/nodes.py`                                                                                              | 1. **创建 Creation 专属 Prompt 模板**（PlannerNode、WriterNode、ReducerNode）<br>2. PlannerNode：调用 LLM 生成大纲，绑定 TavilySearch 工具<br>3. WriterNode：并发节点，生成单章内容<br>4. ReducerNode：合并章节，润色过渡段                                                               | 350  | `langchain-core`, `app.graph.common`, `app.graph.tools`               |
| **Task 8**  | Creation Graph 构建  | 是    | `app/graph/creation/builder.py`                                                                                            | 1. 使用 StateGraph 定义节点与边<br>2. 配置 interrupt_before（大纲确认点）<br>3. 实现 Map Edge（Send API 扇出）<br>4. 编译图并返回单例                                                                | 200  | `langgraph`                                                           |
| **Task 9**  | Polishing State 定义 | 是    | `app/graph/polishing/state.py`                                                                                             | 1. 定义 PolishingState TypedDict<br>2. 定义 DebateState TypedDict（用于子图）                                                                                                   | 60   | `typing`, `langgraph`                                                 |
| **Task 10** | Polishing Prompts 与节点实现     | 是    | `app/graph/polishing/prompts.py`, `app/graph/polishing/nodes.py`                                                                                             | 1. **创建 Polishing 专属 Prompt 模板**（RouterNode、FormatterNode、FactCheckerNode、AuthorNode、EditorNode）<br>2. RouterNode：条件路由逻辑<br>3. FormatterNode：单次格式化<br>4. FactCheckerNode：调用工具进行事实核查<br>5. AuthorNode：重写内容<br>6. EditorNode：打分与反馈                                          | 400  | `langchain-core`, `app.graph.common`, `app.graph.tools`               |
| **Task 11** | Debate Subgraph 构建 | 否    | `app/graph/polishing/debate_graph.py`                                                                                      | 1. 定义 Author-Editor 对抗循环<br>2. 配置条件边（score >= 90 或 iteration >= 3 结束）<br>3. 编译子图并导出                                                                                   | 150  | `langgraph`                                                           |
| **Task 12** | Polishing Graph 构建 | 否    | `app/graph/polishing/builder.py`                                                                                           | 1. 定义主图节点与条件边<br>2. 集成 Debate Subgraph<br>3. 实现三档模式路由（Mode 1/2/3）<br>4. 编译图并返回单例                                                                                      | 220  | `langgraph`, `app.graph.polishing.debate_graph`                       |
| **Task 13** | Checkpointer 与服务层  | 否    | `app/services/checkpointer.py`, `app/services/creation_svc.py`, `app/services/polishing_svc.py`                            | 1. 实现 Checkpointer 单例（开发用 MemorySaver，生产用 PostgresSaver）<br>2. 封装 Creation 业务逻辑（启动、恢复、状态查询）<br>3. 封装 Polishing 业务逻辑                                                   | 400  | `langgraph-checkpoint`, `langgraph-checkpoint-postgres`               |
| **Task 14** | FastAPI 路由层        | 否    | `app/api/dependencies.py`, `app/api/v1/creation.py`, `app/api/v1/polishing.py`, `app/api/v1/router.py`                     | 1. 实现依赖注入（Graph 实例、Checkpointer）<br>2. 实现 Creation 路由（POST /creation, GET /tasks/{id}, POST /tasks/{id}/resume）<br>3. 实现 Polishing 路由（POST /polishing）<br>4. 聚合路由到 v1 | 350  | `fastapi`                                                             |
| **Task 15** | 应用入口与生命周期          | 否    | `app/main.py`                                                                                                              | 1. 创建 FastAPI 应用实例<br>2. 挂载 CORS 中间件<br>3. 注册全局异常处理器<br>4. 实现 startup 事件（初始化 Checkpointer、LLM）<br>5. 实现 shutdown 事件（清理资源）<br>6. 注册 v1 路由                              | 150  | `fastapi`, `uvicorn`                                                  |
| **Task 16** | 测试框架搭建             | 否    | `tests/conftest.py`, `tests/test_api/test_creation.py`, `tests/test_graph/test_creation_graph.py`                          | 1. 配置 Pytest 异步支持<br>2. 创建测试夹具（mock LLM、测试客户端）<br>3. 编写 Creation Graph 单元测试<br>4. 编写 Creation API 端到端测试                                                               | 300  | `pytest`, `pytest-asyncio`, `httpx`                                   |

---

## 三、Prompt 管理策略

详细内容请参见 [Prompt 管理策略](./supplementar/prompt_management_strategy.md)。

### 设计原则

为了保持代码的高内聚低耦合，Prompt 模板按照以下原则组织：

#### 1. **通用 Prompt** → `app/graph/common/prompts.py`

**存放内容**：
- 跨模块可复用的通用模板
- 输出格式规范（如：Markdown 格式要求、JSON Schema 定义）
- 通用角色定义（如：专业技术写作者、编辑的基础人设）
- 通用约束条件（如：禁止幻觉、事实核查要求）

**示例**：
```python
# app/graph/common/prompts.py
MARKDOWN_FORMAT_TEMPLATE = """
输出必须严格遵循 Markdown 格式：
- 使用 # ## ### 表示标题层级
- 代码块使用 ```语言名 包裹
- 链接格式：[文本](URL)
"""

PROFESSIONAL_WRITER_ROLE = """
你是一位资深技术写作专家，擅长将复杂概念转化为清晰易懂的文章。
"""
```

#### 2. **业务专属 Prompt** → 各模块的 `prompts.py`

**存放内容**：
- 特定节点的专属提示词
- 业务逻辑相关的指令
- 模块特有的输入输出格式

**示例**：
```python
# app/graph/creation/prompts.py
PLANNER_SYSTEM_PROMPT = """
你是一位专业的内容策划师，负责根据主题生成结构化大纲...
"""

WRITER_SYSTEM_PROMPT = """
你是一位专业的章节撰写者，负责根据大纲撰写单个章节...
"""

# app/graph/polishing/prompts.py
EDITOR_SCORING_PROMPT = """
你是一位严格的主编，负责对文章进行多维度打分...
"""
```

### 文件组织结构

```
app/graph/
├── common/
│   └── prompts.py          # ✅ 通用、跨模块可复用的模板
├── creation/
│   ├── prompts.py          # ✅ Creation 专属（Planner、Writer、Reducer）
│   └── nodes.py            # 导入 creation.prompts
└── polishing/
    ├── prompts.py          # ✅ Polishing 专属（Router、Formatter、FactChecker、Author、Editor）
    └── nodes.py            # 导入 polishing.prompts
```

### 优势

1. **高内聚**：业务逻辑与提示词在同一模块，便于维护
2. **低耦合**：通用模板独立，避免循环依赖
3. **易扩展**：新增节点只需在对应模块添加 Prompt
4. **清晰职责**：一眼看出哪些是通用的，哪些是业务专属的

---

## 四、开发顺序建议

### 阶段一：基础设施（Task 1-3）
- 目标：搭建项目骨架，确保配置、日志、异常处理可用
- 验证方式：运行 `python -m app.core.config` 能正确读取环境变量

### 阶段二：LLM 与工具链（Task 4-5）
- 目标：确保 LLM 工厂与工具封装可独立测试
- 验证方式：编写简单脚本调用 LLM 与 TavilySearch，确认返回结果

### 阶段三：Creation Graph（Task 6-8）
- 目标：实现完整的创作流状态机
- 验证方式：使用 LangGraph Studio 或单元测试验证图流转逻辑

### 阶段四：Polishing Graph（Task 9-12）
- 目标：实现多阶润色流与子图复用
- 验证方式：单元测试验证条件路由与对抗循环

### 阶段五：服务层与 API（Task 13-15）
- 目标：将图封装为 RESTful 服务
- 验证方式：使用 Postman/curl 测试完整 API 流程

### 阶段六：测试与优化（Task 16）
- 目标：确保代码质量与可维护性
- 验证方式：pytest 覆盖率 > 80%

---

## 五、核心依赖库清单

```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.115.0"
uvicorn = {extras = ["standard"], version = "^0.32.0"}
pydantic = "^2.10.0"
pydantic-settings = "^2.7.0"
langgraph = "^0.2.60"
langgraph-checkpoint = "^2.0.10"
langgraph-checkpoint-postgres = "^2.0.14"
langchain = "^0.3.14"
langchain-core = "^0.3.28"
langchain-openai = "^0.2.14"
langchain-anthropic = "^0.3.3"
langchain-community = "^0.3.13"
tavily-python = "^0.5.0"
e2b-code-interpreter = "^1.0.4"
requests = "^2.32.3"
beautifulsoup4 = "^4.12.3"
loguru = "^0.7.3"
python-dotenv = "^1.0.1"
asyncpg = "^0.30.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.4"
pytest-asyncio = "^0.24.0"
httpx = "^0.28.1"
black = "^24.10.0"
ruff = "^0.8.4"
```

---

## 六、关键技术决策记录

| 决策点       | 选型                                 | 理由                                |
|-----------|------------------------------------|-----------------------------------|
| **状态持久化** | PostgresSaver（生产）/ MemorySaver（开发） | LangGraph 原生支持，避免自研状态管理           |
| **异步框架**  | FastAPI + asyncio                  | 高性能异步 I/O，与 LangGraph 异步 API 无缝集成 |
| **日志方案**  | loguru                             | 结构化日志，开箱即用，比标准 logging 更优雅        |
| **工具绑定**  | LangChain @tool + bind_tools()     | 标准化工具调用，支持自动 schema 生成            |
| **测试框架**  | pytest + pytest-asyncio            | 异步测试支持，夹具机制强大                     |
| **代码质量**  | black + ruff                       | 自动格式化 + 快速 linting                |

---

## 七、风险与缓解措施

| 风险                    | 影响                     | 缓解措施                                     |
|-----------------------|------------------------|------------------------------------------|
| **LLM API 限流**        | 高并发场景下 WriterNode 可能失败 | 1. 实现指数退避重试<br>2. 配置 Rate Limiter（Redis） |
| **Checkpointer 状态膨胀** | MemorySaver 长期运行内存泄漏   | 1. 开发环境定期清理<br>2. 生产环境强制使用 PostgresSaver |
| **工具调用超时**            | E2B 沙箱或搜索 API 响应慢      | 1. 设置工具调用超时（30s）<br>2. 降级策略（跳过工具，记录日志）   |
| **图状态不一致**            | 并发修改同一 thread_id       | 1. 业务层加锁（Redis 分布式锁）<br>2. 前端禁止并发提交      |

---

## 八、后续扩展方向

1. **流式响应**：使用 `graph.astream_events()` 实现 SSE，提升用户体验
2. **多租户隔离**：在 Checkpointer 中增加 `namespace` 维度
3. **可观测性**：集成 LangSmith 追踪，监控每个节点的 Token 消耗与耗时
4. **RAG 增强**：完善 `LocalKnowledge_Retriever`，支持 PDF/DOCX 上传与向量化
5. **前端集成**：提供 WebSocket 接口，实时推送图执行状态

---

**文档版本**: v1.0  
**最后更新**: 2026-04-30  
**维护者**: CraftFlow 开发团队
