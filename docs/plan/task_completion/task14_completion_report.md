# Task 14 完成报告：FastAPI 路由层

## 任务概述

**任务名称**: FastAPI 路由层  
**任务 ID**: Task 14  
**完成日期**: 2026-05-04  
**状态**: ✅ 已完成  

## 实现内容

### 1. 依赖注入模块

创建了 [dependencies.py](app/api/dependencies.py)，提供全局服务实例的 FastAPI 依赖注入：

- `init_services()`: 应用启动时初始化 CreationService 和 PolishingService
- `close_services()`: 应用关闭时释放资源
- `get_creation_service()`: FastAPI `Depends()` 注入 CreationService
- `get_polishing_service()`: FastAPI `Depends()` 注入 PolishingService

依赖链：`checkpointer → init_services() → get_creation_service() / get_polishing_service()`

### 2. Creation 路由

创建了 [creation.py](app/api/v1/creation.py)，提供创作任务的 RESTful 接口：

| 方法 | 路径 | 说明 | 状态码 |
|------|------|------|--------|
| POST | `/creation` | 创建创作任务 | 201 |
| GET | `/tasks/{task_id}` | 查询任务状态 | 200 |
| POST | `/tasks/{task_id}/resume` | 恢复中断的任务（HITL） | 200 |

路由特性：
- 使用 `Depends(get_creation_service)` 注入服务
- GET 端点支持 `include_state` 和 `include_history` 查询参数
- POST resume 端点支持 `confirm_outline` / `update_outline` 动作
- 错误通过全局异常处理器统一返回 `ErrorResponse`

### 3. Polishing 路由

创建了 [polishing.py](app/api/v1/polishing.py)，提供润色任务的 RESTful 接口：

| 方法 | 路径 | 说明 | 状态码 |
|------|------|------|--------|
| POST | `/polishing` | 创建润色任务（三档模式） | 201 |

支持模式：
- Mode 1: 极速格式化
- Mode 2: 专家对抗审查（默认）
- Mode 3: 事实核查

### 4. 路由聚合

创建了 [router.py](app/api/v1/router.py)，将 v1 版本的所有路由聚合到统一的 `APIRouter`：

- 前缀: `/api/v1`
- 包含 Creation 和 Polishing 路由
- 在 `app/main.py` 中通过 `include_router` 注册

### 5. 异常处理器修复

修复了 [exceptions.py](app/core/exceptions.py) 中的 `validation_exception_handler`：

- 新增 `_clean_validation_errors()` 辅助函数
- 清理 Pydantic 验证错误中不可序列化的 `ValueError` 对象
- 将 `ctx` 字段中的 Exception 对象转换为字符串

### 6. 包导出更新

更新了 `app/api/__init__.py` 和 `app/api/v1/__init__.py`，统一导出依赖注入函数和路由。

## 关键设计决策

### 1. 依赖注入模式

使用 FastAPI 的 `Depends()` 机制注入服务层：

```python
@router.post("/creation")
async def create_creation_task(
    request: CreationRequest,
    service: CreationService = Depends(get_creation_service),
) -> TaskResponse:
    return await service.start_task(topic=request.topic, ...)
```

- 服务实例在应用启动时通过 `init_services()` 创建
- 依赖函数 `get_creation_service()` 返回模块级单例
- 测试中通过 `app.dependency_overrides` 覆盖依赖

### 2. 请求-响应模型复用

完全复用 `app/schemas/` 中已有的 Pydantic 模型：
- 请求: `CreationRequest`, `PolishingRequest`, `ResumeRequest`, `TaskQueryParams`
- 响应: `TaskResponse`, `TaskStatusResponse`, `ResumeResponse`, `ErrorResponse`

### 3. 全局异常处理

所有业务异常通过 `register_exception_handlers(app)` 统一处理：
- `CraftFlowException` → 对应 HTTP 状态码 + `ErrorResponse`
- `RequestValidationError` → 422 + 清理后的错误详情
- `Exception` → 500 + 通用错误信息

### 4. 测试策略

API 测试使用 `httpx.AsyncClient` + `ASGITransport`：
- 每个测试创建独立的 FastAPI 应用实例
- 通过 `dependency_overrides` 全局覆盖服务依赖
- 验证请求参数验证（422）、成功响应（201/200）和错误响应（404/500）

## 测试覆盖

| 测试文件 | 测试数量 | 覆盖内容 |
|----------|----------|----------|
| `test_creation_api.py` | 15 | POST /creation、GET /tasks、POST /tasks/resume |
| `test_polishing_api.py` | 9 | POST /polishing 三档模式、参数验证、错误处理 |

**测试结果**: ✅ 165 passed（含 Creation/Polishing Graph、Services 和 Schemas 测试）

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/api/dependencies.py` | 新建 | FastAPI 依赖注入模块 |
| `app/api/v1/creation.py` | 新建 | Creation 路由 |
| `app/api/v1/polishing.py` | 新建 | Polishing 路由 |
| `app/api/v1/router.py` | 新建 | v1 路由聚合 |
| `app/api/__init__.py` | 修改 | 添加依赖注入和路由导出 |
| `app/api/v1/__init__.py` | 修改 | 添加路由导出 |
| `app/core/exceptions.py` | 修改 | 修复 validation_exception_handler 序列化问题 |
| `tests/test_api/test_creation_api.py` | 新建 | Creation API 测试 |
| `tests/test_api/test_polishing_api.py` | 新建 | Polishing API 测试 |

## 代码质量

- ✅ 完整的类型注解
- ✅ Google 风格 Docstring
- ✅ OpenAPI 文档自动生成（FastAPI 内置）
- ✅ 全局异常处理器统一错误格式
- ✅ 依赖注入支持测试覆盖
- ✅ 全量 165 个测试通过

## 后续依赖

本任务的完成为以下任务奠定基础：
- **Task 15**: 应用入口（将调用 `init_services()` 和 `register_exception_handlers()`）
- **Task 16**: 启动应用（可通过 `uvicorn app.main:app` 启动并访问 /docs）

---

**完成时间**: 2026-05-04  
**执行者**: Claude Code
