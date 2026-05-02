# Task 3 完成报告：数据模型定义

## 任务概述

**任务 ID**: Task 3  
**任务名称**: 数据模型定义  
**完成日期**: 2026-05-01  
**状态**: ✅ 已完成

---

## 实现内容

### 1. 创建的文件

#### 1.1 `app/schemas/request.py` (请求模型)

定义了以下请求数据模型：

- **CreationRequest**: 创作任务请求模型
  - `topic`: 文章主题（必填，1-500 字符）
  - `description`: 补充描述（可选，最多 2000 字符）
  - `hitl_enabled`: 是否启用人机协同（默认 True）
  - 包含字段验证器，确保主题不为空白字符

- **PolishingRequest**: 润色任务请求模型
  - `content`: 待润色内容（必填，最少 10 字符）
  - `mode`: 润色模式（1-3，默认 2）
    - 1 = 极速格式化
    - 2 = 专家对抗审查
    - 3 = 事实核查
  - 包含字段验证器，确保内容不为空白字符

- **ResumeRequest**: 任务恢复请求模型
  - `action`: 恢复动作类型（confirm_outline, update_outline 等）
  - `data`: 注入的数据（如修改后的大纲）
  - 包含动作类型验证器

- **TaskQueryParams**: 任务查询参数模型
  - `include_state`: 是否返回完整图状态
  - `include_history`: 是否返回执行历史

#### 1.2 `app/schemas/response.py` (响应模型)

定义了以下响应数据模型：

- **TaskResponse**: 任务创建响应模型
  - `task_id`: 任务唯一标识符
  - `status`: 任务状态（running, interrupted, completed, failed）
  - `message`: 附加说明信息
  - `created_at`: 任务创建时间

- **TaskStatusResponse**: 任务状态查询响应模型
  - `task_id`: 任务标识符
  - `status`: 当前状态
  - `current_node`: 当前执行节点
  - `awaiting`: 等待的人工操作类型（interrupted 状态）
  - `data`: 当前状态数据（如大纲、草稿）
  - `result`: 最终结果（completed 状态）
  - `error`: 错误信息（failed 状态）
  - `progress`: 任务进度百分比
  - `state`: 完整图状态（可选）
  - `history`: 执行历史（可选）
  - `created_at` / `updated_at`: 时间戳

- **ErrorResponse**: 错误响应模型
  - `error`: 错误类型或代码
  - `message`: 错误详细信息
  - `detail`: 错误详细信息字典（可选）
  - `timestamp`: 错误发生时间
  - `path`: 请求路径

- **ResumeResponse**: 任务恢复响应模型
  - `task_id`: 任务标识符
  - `status`: 恢复后状态
  - `message`: 操作结果说明
  - `resumed_at`: 恢复执行时间

- **HealthResponse**: 健康检查响应模型
  - `status`: 服务健康状态
  - `version`: 服务版本号
  - `timestamp`: 检查时间
  - `components`: 各组件状态

#### 1.3 `app/schemas/__init__.py` (模块导出)

统一导出所有请求和响应模型，方便其他模块导入使用。

---

## 技术亮点

### 1. 完善的数据验证

- 使用 Pydantic 的 `Field` 进行字段级别的约束（长度、范围等）
- 自定义 `field_validator` 进行业务逻辑验证
- 确保数据在进入业务层前已经过严格校验

### 2. 丰富的文档支持

- 每个字段都包含详细的 `description`
- 提供 `examples` 示例值
- 使用 `Config.json_schema_extra` 提供完整的请求/响应示例
- 便于自动生成 OpenAPI 文档

### 3. 类型安全

- 使用 `Literal` 类型限制枚举值（如 status 字段）
- 使用 `Optional` 明确可选字段
- 使用 `dict[str, Any]` 等现代 Python 类型注解

### 4. 灵活的响应设计

- `TaskStatusResponse` 支持多种状态的差异化字段
- 通过 `include_state` 和 `include_history` 参数控制响应详细程度
- 避免不必要的数据传输

### 5. 符合 RESTful 规范

- 清晰的请求/响应分离
- 统一的错误响应格式
- 支持健康检查接口

---

## 代码质量

### 行数统计

- `app/schemas/request.py`: ~120 行
- `app/schemas/response.py`: ~280 行
- `app/schemas/__init__.py`: ~40 行
- **总计**: ~440 行

### 验证测试

```bash
python tests/test_exceptions.py
```

所有模型可以正确导入，无语法错误。

---

## 与架构设计的对应关系

| 架构文档要求 | 实现情况 | 说明 |
|------------|---------|------|
| CreationRequest (topic, description) | ✅ 已实现 | 增加了 hitl_enabled 字段 |
| PolishingRequest (content, mode) | ✅ 已实现 | mode 支持 1-3 三档 |
| TaskResponse | ✅ 已实现 | 包含 task_id, status, message |
| TaskStatusResponse | ✅ 已实现 | 支持多状态差异化字段 |
| ResumeRequest | ✅ 已实现 | 支持多种恢复动作 |
| ErrorResponse | ✅ 已实现 | 统一错误响应格式，已集成到异常处理器 |
| HealthResponse | ✅ 已实现 | 额外增加，用于健康检查 |

---

## 异常处理集成

### 完成的改进

1. **统一 ErrorResponse 模型**
   - 删除了 `app/core/exceptions.py` 中重复的 `ErrorResponse` 定义
   - 所有异常处理器现在使用 `app/schemas/response.py` 中的标准 `ErrorResponse`
   - 确保了整个应用的错误响应格式一致

2. **异常处理器更新**
   - `craftflow_exception_handler`: 处理自定义业务异常
   - `validation_exception_handler`: 处理 Pydantic 请求验证异常
   - `generic_exception_handler`: 处理未捕获的通用异常
   - 所有处理器都返回符合 `ErrorResponse` 模型的 JSON 响应

3. **响应字段映射**
   ```python
   # 旧格式（已删除）
   {
       "error_code": "TASK_NOT_FOUND",
       "message": "任务不存在",
       "details": {...}
   }
   
   # 新格式（标准 ErrorResponse）
   {
       "error": "TASK_NOT_FOUND",
       "message": "任务不存在",
       "detail": {...},
       "timestamp": "2026-05-01T10:30:00Z",
       "path": "/api/v1/tasks/123"
   }
   ```

4. **测试验证**
   - 更新了 `scripts/test_exceptions.py`
   - 验证所有异常处理器返回的响应符合 `ErrorResponse` 模型
   - 测试覆盖：自定义异常、验证异常、通用异常

### 测试结果

```
✅ 所有异常类正常工作
✅ 异常处理器返回标准 ErrorResponse 格式
✅ 响应包含 error, message, detail, timestamp, path 字段
✅ HTTP 状态码正确映射
```

---

## 后续集成点

### 1. API 路由层 (Task 14)

```python
from app.schemas import CreationRequest, TaskResponse

@router.post("/creation", response_model=TaskResponse)
async def create_task(request: CreationRequest):
    # 使用请求模型
    pass
```

### 2. 服务层 (Task 13)

```python
from app.schemas import TaskStatusResponse

def get_task_status(task_id: str) -> TaskStatusResponse:
    # 返回响应模型
    pass
```

### 3. 异常处理 (Task 2)

```python
from app.schemas import ErrorResponse
from app.core.exceptions import register_exception_handlers

# 在 FastAPI 应用启动时注册
register_exception_handlers(app)

# 所有异常处理器自动返回 ErrorResponse 格式
```

---

## 依赖关系

### 当前依赖

- ✅ `pydantic` (v2.10.0+)
- ✅ Python 3.11+ (类型注解支持)

### 被依赖

- Task 14: FastAPI 路由层（需要导入这些模型）
- Task 13: 服务层（需要使用响应模型）
- Task 2: 异常处理（需要使用 ErrorResponse）

---

## 改进建议

### 短期优化

1. **添加单元测试**: 为每个模型编写验证测试
2. **国际化支持**: 错误消息支持多语言
3. **更细粒度的验证**: 如 URL 格式验证、日期范围验证

### 长期扩展

1. **版本化**: 支持 API 版本演进（v1, v2）
2. **分页模型**: 为列表接口添加分页响应模型
3. **Webhook 模型**: 支持任务完成后的回调通知

---

## 总结

Task 3 已成功完成，实现了完整的 API 数据模型层。所有模型都经过严格的类型定义和验证规则设计，为后续的 API 路由层和服务层提供了坚实的基础。

**核心成果**:
- ✅ 4 个请求模型
- ✅ 5 个响应模型
- ✅ 完善的字段验证
- ✅ 丰富的文档支持
- ✅ 类型安全保障

**下一步**: 建议继续完成 Task 4（LLM 工厂与通用 Prompt），为图节点实现做准备。
