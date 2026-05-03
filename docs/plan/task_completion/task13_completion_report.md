# Task 13 完成报告：Checkpointer 与服务层

## 任务概述

**任务名称**: Checkpointer 与服务层  
**任务 ID**: Task 13  
**完成日期**: 2026-05-03  
**状态**: ✅ 已完成  

## 实现内容

### 1. Checkpointer 管理模块

创建了 [checkpointer.py](app/services/checkpointer.py)，实现 Checkpointer 单例管理：

- `init_checkpointer()`: 根据 `settings.use_persistent_checkpointer` 初始化 MemorySaver 或 PostgresSaver
- `get_checkpointer()`: 获取已初始化的 Checkpointer 实例
- `close_checkpointer()`: 关闭 Checkpointer，释放资源（PostgresSaver 关闭连接池）
- `reset_checkpointer()`: 重置单例（仅用于测试）

支持两种模式：
- **开发环境**: MemorySaver（内存存储，进程退出即丢失）
- **生产环境**: AsyncPostgresSaver（PostgreSQL 持久化存储）

### 2. Graph Builder 改造

修改了 Creation 和 Polishing 的 Graph Builder，支持 Checkpointer 注入：

#### Creation Graph Builder

修改了 [builder.py](app/graph/creation/builder.py)：
- 移除 `@lru_cache` 装饰器（缓存由服务层管理）
- `get_creation_graph(checkpointer=None)` 接受可选的 Checkpointer 参数
- `.compile(checkpointer=checkpointer, interrupt_before=["outline_confirmation"])`
- 移除 `creation_graph` 模块级别名（不再适用）

#### Polishing Graph Builder

修改了 [builder.py](app/graph/polishing/builder.py)：
- 移除 `@lru_cache` 装饰器
- `get_polishing_graph(checkpointer=None)` 接受可选的 Checkpointer 参数
- `.compile(checkpointer=checkpointer)`

### 3. Creation 业务服务层

创建了 [creation_svc.py](app/services/creation_svc.py)，封装 Creation Graph 的完整生命周期：

#### CreationService 类

| 方法 | 功能 | 说明 |
|------|------|------|
| `start_task(topic, description)` | 创建并启动创作任务 | 执行 PlannerNode 后在 outline_confirmation 中断点暂停 |
| `resume_task(task_id, action, data)` | 恢复被中断的任务 | 支持 confirm_outline / update_outline |
| `get_task_status(task_id, ...)` | 查询任务状态 | 返回 current_node、progress、result 等 |

关键设计：
- **thread_id = task_id**: 简化映射关系
- **GraphInterrupt 捕获**: 检测 HITL 中断，标记任务状态为 "interrupted"
- **任务元数据管理**: 维护 status、created_at、updated_at 等
- **进度计算**: 根据 current_node 计算百分比（planner 20% → reducer 80% → completed 100%）

### 4. Polishing 业务服务层

创建了 [polishing_svc.py](app/services/polishing_svc.py)，封装 Polishing Graph 的业务逻辑：

#### PolishingService 类

| 方法 | 功能 | 说明 |
|------|------|------|
| `start_task(content, mode)` | 创建并执行润色任务 | 三档模式：极速格式化/专家对抗审查/事实核查 |
| `get_task_status(task_id, ...)` | 查询任务状态 | 返回 current_node、progress、result 等 |

关键设计：
- **无 HITL**: Polishing Graph 无中断点，任务直接执行至完成
- **结果提取**: `_extract_result()` 按优先级从 final_content / formatted_content / fact_check_result 提取
- **状态序列化**: `_serialize_state()` 处理 DebateRound、ScoreDetail 等 TypedDict 的序列化

### 5. 服务层导出

更新了 [__init__.py](app/services/__init__.py)，统一导出：
- `init_checkpointer`, `get_checkpointer`, `close_checkpointer`
- `CreationService`, `PolishingService`

## 关键设计决策

### 1. 图构建与编译分离

移除了 Graph Builder 上的 `@lru_cache`，将缓存职责移至服务层：
- `build_creation_graph()` 构建未编译的 StateGraph（可缓存）
- `get_creation_graph(checkpointer)` 每次编译新图（服务层缓存编译结果）
- 原因：`lru_cache` 无法正确处理 mutable 的 Checkpointer 实例

### 2. GraphInterrupt 替代 NodeInterrupt

使用 `langgraph.errors.GraphInterrupt`（替代已弃用的 `NodeInterrupt`）捕获 HITL 中断。`GraphInterrupt` 是 `NodeInterrupt` 的父类，兼容新旧两种中断方式。

### 3. 任务状态独立管理

任务元数据（status、timestamps）存储在服务层的 `_tasks` 字典中，与 LangGraph 的 Checkpoint 分离：
- 便于快速查询任务状态（无需解析 Checkpoint）
- 便于后续替换为 Redis/DB 持久化
- 当前为内存存储，适合开发阶段

### 4. 惰性图初始化

服务层使用 `_get_graph()` 惰性初始化编译后的图实例：
- 首次调用时编译图并注入 Checkpointer
- 后续调用返回缓存的编译实例
- 避免在服务构造时就编译图

## 测试覆盖

| 测试文件 | 测试数量 | 覆盖内容 |
|----------|----------|----------|
| `test_checkpointer.py` | 11 | 初始化、获取、关闭、重置、PostgresSaver 模式 |
| `test_creation_svc.py` | 18 | 任务创建、中断、恢复、状态查询、进度计算 |
| `test_polishing_svc.py` | 23 | 三档模式创建、状态查询、结果提取、进度计算 |

**测试结果**: ✅ 141 passed（含 Creation/Polishing Graph 和 Schemas 测试）

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/services/checkpointer.py` | 新建 | Checkpointer 单例管理 |
| `app/services/creation_svc.py` | 新建 | Creation 业务服务层 |
| `app/services/polishing_svc.py` | 新建 | Polishing 业务服务层 |
| `app/services/__init__.py` | 修改 | 添加服务层导出 |
| `app/graph/creation/builder.py` | 修改 | 移除 lru_cache，添加 checkpointer 参数 |
| `app/graph/creation/__init__.py` | 修改 | 移除 creation_graph 导出 |
| `app/graph/polishing/builder.py` | 修改 | 移除 lru_cache，添加 checkpointer 参数 |
| `tests/test_services/__init__.py` | 新建 | 测试包标识 |
| `tests/test_services/test_checkpointer.py` | 新建 | Checkpointer 测试 |
| `tests/test_services/test_creation_svc.py` | 新建 | Creation 服务测试 |
| `tests/test_services/test_polishing_svc.py` | 新建 | Polishing 服务测试 |
| `tests/test_graph/test_creation_graph.py` | 修改 | 移除 cache_clear 调用 |
| `tests/test_graph/test_polishing_graph.py` | 修改 | 移除 cache_clear 调用和单例测试 |

## 代码质量

- ✅ 完整的类型注解
- ✅ Google 风格 Docstring
- ✅ 结构化日志记录
- ✅ GraphInterrupt 异常处理（替代已弃用的 NodeInterrupt）
- ✅ 服务层与 Graph 层解耦
- ✅ Checkpointer 单例管理
- ✅ 全量 141 个测试通过

## 后续依赖

本任务的完成为以下任务奠定基础：
- **Task 14**: FastAPI 路由层（将通过依赖注入获取 CreationService / PolishingService）
- **Task 15**: 应用入口（startup 事件中调用 init_checkpointer()）

---

**完成时间**: 2026-05-03  
**执行者**: Claude Code
