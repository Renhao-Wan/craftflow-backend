# Task 15 完成报告：应用入口与生命周期

## 任务概述

**任务名称**: 应用入口与生命周期  
**任务 ID**: Task 15  
**完成日期**: 2026-05-04  
**状态**: ✅ 已完成  

## 实现内容

### 1. 应用入口模块

创建了 [main.py](app/main.py)，提供 FastAPI 应用的完整入口：

- `create_app()`: 工厂函数，创建并配置 FastAPI 应用实例
- `lifespan()`: 异步上下文管理器，管理 startup/shutdown 生命周期
- `app`: 模块级应用实例，可直接被 uvicorn 引用

### 2. 生命周期管理

使用 `@asynccontextmanager` + `lifespan` 参数（替代已废弃的 `@app.on_event`）：

**Startup 阶段**：
1. `setup_logger()` — 初始化日志系统
2. `init_checkpointer()` — 初始化 Checkpointer 单例
3. `init_services()` — 初始化 CreationService 和 PolishingService

**Shutdown 阶段**：
1. `close_services()` — 释放业务服务资源
2. `close_checkpointer()` — 关闭 Checkpointer（PostgresSaver 关闭连接池）

### 3. CORS 中间件

从 `settings` 读取配置，挂载 `CORSMiddleware`：

- `allow_origins`: 从 `settings.cors_origins`（逗号分隔字符串，经 `@field_validator` 解析为 list）
- `allow_credentials`: `settings.cors_allow_credentials`
- `allow_methods`: `["*"]`
- `allow_headers`: `["*"]`

### 4. 全局异常处理器

通过 `register_exception_handlers(app)` 注册：
- `CraftFlowException` → 对应 HTTP 状态码 + `ErrorResponse`
- `RequestValidationError` → 422 + 清理后的错误详情
- `Exception` → 500 + 通用错误信息

### 5. 路由注册

- v1 路由: `app.include_router(v1_router)`（前缀 `/api/v1`）
- 健康检查: `GET /health` 返回 `{"status": "ok", "version": "...", "environment": "..."}`

### 6. OpenAPI 文档

开发环境自动启用 `/docs`（Swagger UI）和 `/redoc`（ReDoc），生产环境关闭。

## 关键设计决策

### 1. lifespan 替代 on_event

FastAPI 0.103+ 推荐使用 `lifespan` 参数替代 `@app.on_event("startup")`：

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # startup
    await init_checkpointer()
    await init_services()
    yield
    # shutdown
    await close_services()
    await close_checkpointer()
```

优势：类型安全、支持依赖注入、生命周期状态明确。

### 2. 工厂函数模式

`create_app()` 工厂函数使得测试可以创建独立的应用实例，避免模块级 `app` 的副作用。

### 3. CORS origins 解析

`settings.cors_origins` 是 `str` 类型，通过 `@field_validator("cors_origins")` 在 Settings 初始化时解析为 `list[str]`。直接使用 `settings.cors_origins`（已经是 list）即可，无需再次调用解析函数。

## 测试覆盖

| 测试文件 | 测试数量 | 覆盖内容 |
|----------|----------|----------|
| `test_main.py` | 9 | 应用创建、元数据、路由注册、健康检查、CORS、异常处理器、生命周期 |

**测试结果**: ✅ 174 passed（含之前所有测试）

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/main.py` | 新建 | FastAPI 应用入口，含 lifespan、CORS、路由注册 |
| `tests/test_main.py` | 新建 | 应用入口测试（9 个测试） |

## 代码质量

- ✅ 完整的类型注解
- ✅ Google 风格 Docstring
- ✅ lifespan 异步上下文管理器（非废弃 API）
- ✅ 工厂函数模式支持测试
- ✅ 全量 174 个测试通过

## 后续依赖

本任务的完成为以下任务奠定基础：
- **Task 16**: 启动应用（可通过 `uv run uvicorn app.main:app --reload` 启动并访问 /docs）

---

**完成时间**: 2026-05-04  
**执行者**: Claude Code
