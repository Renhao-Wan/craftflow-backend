# CraftFlow Backend

> 基于 Agentic Workflow 的智能长文织造与多阶审校平台

## 项目简介

**CraftFlow** 是一个创新的 AI 内容创作平台，采用 LangGraph 驱动的双轨状态机架构，彻底解决大语言模型在长文生成中的质量失控问题。

### 核心特性

- 🎯 **渐进式织造 (Map-Reduce)**：大纲先行 + 并发撰写，突破上下文长度限制
- 🔄 **多阶审校流**：极速格式化 / 专家对抗 / 事实核查三档弹性算力
- 🤝 **强制人机协同 (HITL)**：关键决策点自动挂起，支持断点续传
- 🛠️ **工具链增强**：集成搜索、代码沙箱、链接验证等外部工具
- 📊 **长周期有状态任务**：基于 Checkpointer 的持久化状态管理

### 技术栈

- **后端框架**: Python 3.11+, FastAPI, Pydantic V2
- **AI 编排**: LangGraph, LangChain
- **持久化**: PostgreSQL (pgvector), Redis
- **LLM**: OpenAI / Anthropic / DeepSeek (可配置)

## 快速开始

### 环境要求

- Python 3.11+
- Poetry (推荐) 或 pip
- PostgreSQL 14+ (生产环境)
- Redis (可选，用于限流)

### 安装步骤

1. **克隆项目**

```bash
git clone https://github.com/your-org/craftflow-backend.git
cd craftflow-backend
```

2. **安装依赖**

使用 Poetry（推荐）：

```bash
poetry install
```

或使用 pip：

```bash
pip install -r requirements.txt
```

3. **配置环境变量**

```bash
cp .env.example .env.dev
# 编辑 .env.dev，填写必要的 API Key
```

必填配置项：
- `OPENAI_API_KEY` 或其他 LLM Provider 的 API Key
- `TAVILY_API_KEY`（用于互联网搜索）
- `E2B_API_KEY`（用于代码沙箱，可选）

4. **启动开发服务器**

```bash
poetry run uvicorn app.main:app --reload --env-file .env.dev
```

或：

```bash
python -m uvicorn app.main:app --reload --env-file .env.dev
```

服务将在 `http://localhost:8000` 启动。

### 验证安装

访问 API 文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 项目结构

```
craftflow-backend/
├── app/
│   ├── api/                    # FastAPI 路由层
│   │   ├── dependencies.py     # 依赖注入
│   │   └── v1/                 # API v1 版本
│   ├── core/                   # 基础设施层
│   │   ├── config.py           # 全局配置
│   │   ├── exceptions.py       # 异常处理
│   │   └── logger.py           # 日志配置
│   ├── graph/                  # LangGraph 核心编排
│   │   ├── common/             # 共享抽象（LLM 工厂、Prompt）
│   │   ├── tools/              # 外部工具封装
│   │   ├── creation/           # Creation Graph 模块
│   │   └── polishing/          # Polishing Graph 模块
│   ├── schemas/                # Pydantic 数据模型
│   ├── services/               # 业务服务层
│   └── main.py                 # 应用入口
├── tests/                      # 测试目录
├── docs/                       # 文档目录
├── logs/                       # 日志目录
├── .env.example                # 环境变量模板
├── pyproject.toml              # 项目依赖配置
└── README.md                   # 本文件
```

## 核心 API

### 1. 创作流 (Creation)

**发起创作任务**

```bash
POST /api/v1/creation
Content-Type: application/json

{
  "topic": "微服务架构演进",
  "description": "面向后端工程师，深度技术文章"
}
```

**响应**

```json
{
  "task_id": "c-uuid-xxx",
  "status": "running"
}
```

**查询任务状态**

```bash
GET /api/v1/tasks/{task_id}
```

**恢复执行（修改大纲后）**

```bash
POST /api/v1/tasks/{task_id}/resume
Content-Type: application/json

{
  "action": "confirm_outline",
  "data": {
    "outline": [...]
  }
}
```

### 2. 润色流 (Polishing)

**发起润色任务**

```bash
POST /api/v1/polishing
Content-Type: application/json

{
  "content": "文章正文...",
  "mode": 3
}
```

模式说明：
- `mode=1`: 极速格式化（单次 LLM 调用）
- `mode=2`: 专家对抗循环（Author-Editor 博弈）
- `mode=3`: 事实核查 + 对抗循环（最高质量）

## 开发指南

### 使用 LangGraph Studio 调试

1. 安装 LangGraph Studio
2. 打开项目目录
3. Studio 会自动读取 `langgraph.json` 配置
4. 可视化调试 Creation Graph 和 Polishing Graph

### 运行测试

```bash
# 运行所有测试
poetry run pytest

# 运行特定测试文件
poetry run pytest tests/test_graph/test_creation_graph.py

# 查看覆盖率
poetry run pytest --cov=app --cov-report=html
```

### 代码格式化

```bash
# 使用 black 格式化
poetry run black app/ tests/

# 使用 ruff 检查
poetry run ruff check app/ tests/
```

## 部署

### 生产环境配置

1. 修改 `.env` 文件：
   - 设置 `ENVIRONMENT=production`
   - 设置 `USE_PERSISTENT_CHECKPOINTER=true`
   - 配置 PostgreSQL 连接字符串
   - 关闭 `DEBUG` 和 `RELOAD`

2. 使用 Gunicorn 部署：

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --env-file .env
```

### Docker 部署（待完善）

```bash
docker build -t craftflow-backend .
docker run -p 8000:8000 --env-file .env craftflow-backend
```

## 架构设计

详细架构文档请参考：

- [架构设计方案](docs/CraftFlow%20架构设计方案.md)
- [核心开发蓝图](docs/CraftFlow%20核心开发蓝图与架构规范.md)
- [开发计划](docs/plan/dev_plan.md)

### 核心设计理念

1. **双图解耦**：Creation Graph 和 Polishing Graph 物理分离
2. **Map-Reduce 并发**：利用 LangGraph `Send` API 实现章节并发生成
3. **子图复用**：Debate Subgraph 作为独立组件被 Polishing Graph 调用
4. **异步优先**：所有 I/O 操作使用 async/await

## 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 联系方式

- 项目主页: https://github.com/your-org/craftflow-backend
- 问题反馈: https://github.com/your-org/craftflow-backend/issues

---

**文档版本**: v1.0  
**最后更新**: 2026-04-30  
**维护者**: CraftFlow 开发团队
