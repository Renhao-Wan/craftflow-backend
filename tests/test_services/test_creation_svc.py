"""Creation 业务服务层测试

测试 CreationService 的任务创建、状态查询和 HITL 恢复逻辑。
使用 mock 隔离 Graph 执行和 Checkpointer。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from langgraph.errors import GraphInterrupt

from app.core.exceptions import GraphExecutionError, TaskNotFoundError
from app.schemas.response import TaskResponse, TaskStatusResponse
from app.services.creation_svc import CreationService


@pytest.fixture
def mock_checkpointer():
    """创建 mock Checkpointer"""
    return MagicMock()


@pytest.fixture
def mock_task_store():
    """创建 mock TaskStore"""
    store = AsyncMock()
    store.save_task = AsyncMock()
    store.get_task = AsyncMock(return_value=None)
    store.get_task_list = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_graph():
    """创建 mock 编译后的 Graph"""
    graph = AsyncMock()
    graph.ainvoke = AsyncMock()
    graph.aget_state = AsyncMock(return_value=MagicMock(values={}))
    graph.aupdate_state = AsyncMock()
    return graph


@pytest.fixture
def service(mock_checkpointer, mock_task_store, mock_graph):
    """创建 CreationService 实例（注入 mock graph）"""
    svc = CreationService(checkpointer=mock_checkpointer, task_store=mock_task_store)
    svc._graph = mock_graph
    return svc


def _setup_graph_mocks(mock_graph, invoke_result, state_values=None):
    """统一设置 ainvoke 和 aget_state 的返回值

    Args:
        mock_graph: mock Graph 实例
        invoke_result: ainvoke 的返回值或 side_effect
        state_values: aget_state 返回的状态值，默认使用 invoke_result
    """
    if isinstance(invoke_result, Exception) or (
        hasattr(invoke_result, "__class__")
        and issubclass(invoke_result.__class__, BaseException)
    ):
        mock_graph.ainvoke.side_effect = invoke_result
    else:
        mock_graph.ainvoke.return_value = invoke_result
        mock_graph.ainvoke.side_effect = None

    state = state_values if state_values is not None else invoke_result
    if isinstance(state, Exception):
        state = {}
    mock_graph.aget_state.return_value = MagicMock(values=state or {})


# ============================================
# start_task 测试
# ============================================


class TestStartTask:
    """测试任务创建"""

    @pytest.mark.asyncio
    async def test_start_task_returns_task_response(self, service, mock_graph):
        """测试创建任务返回 TaskResponse"""
        _setup_graph_mocks(mock_graph, {
            "current_node": "outline_confirmation",
            "outline": [],
        })

        result = await service.start_task(topic="人工智能", description="讨论 AI 发展")

        assert isinstance(result, TaskResponse)
        assert result.task_id.startswith("creation_")
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_start_task_interrupted_at_outline(self, service, mock_graph, mock_task_store):
        """测试任务在大纲确认点中断"""
        _setup_graph_mocks(mock_graph, GraphInterrupt("outline_confirmation"))

        result = await service.start_task(topic="人工智能")

        assert isinstance(result, TaskResponse)
        assert result.status == "interrupted"
        assert "大纲" in result.message

        # 中断任务应持久化到 TaskStore
        mock_task_store.save_task.assert_called_once()
        saved_data = mock_task_store.save_task.call_args[0][0]
        assert saved_data["status"] == "interrupted"
        assert saved_data["topic"] == "人工智能"

    @pytest.mark.asyncio
    async def test_start_task_saves_metadata(self, service, mock_graph, mock_task_store):
        """测试任务元数据正确保存到 TaskStore"""
        _setup_graph_mocks(mock_graph, {"current_node": "reducer"})

        result = await service.start_task(topic="测试主题")

        # 已完成任务应持久化到 TaskStore 并从 _tasks 移除
        mock_task_store.save_task.assert_called_once()
        saved_data = mock_task_store.save_task.call_args[0][0]
        assert saved_data["status"] == "completed"
        assert saved_data["graph_type"] == "creation"
        assert saved_data["topic"] == "测试主题"
        assert result.task_id not in service._tasks

    @pytest.mark.asyncio
    async def test_start_task_graph_error_raises(self, service, mock_graph, mock_task_store):
        """测试图执行错误时抛出 GraphExecutionError"""
        _setup_graph_mocks(mock_graph, RuntimeError("LLM 调用失败"))

        with pytest.raises(GraphExecutionError) as exc_info:
            await service.start_task(topic="测试")

        assert "失败" in str(exc_info.value.message)
        # 失败任务应持久化到 TaskStore
        mock_task_store.save_task.assert_called_once()
        saved_data = mock_task_store.save_task.call_args[0][0]
        assert saved_data["status"] == "failed"
        assert "LLM 调用失败" in saved_data["error"]

    @pytest.mark.asyncio
    async def test_start_task_passes_correct_state(self, service, mock_graph):
        """测试传递正确的初始状态给 Graph"""
        _setup_graph_mocks(mock_graph, {})

        await service.start_task(topic="Python 编程", description="入门教程")

        call_args = mock_graph.ainvoke.call_args
        initial_state = call_args[0][0]

        assert initial_state["topic"] == "Python 编程"
        assert initial_state["description"] == "入门教程"
        assert initial_state["outline"] == []
        assert initial_state["sections"] == []

    @pytest.mark.asyncio
    async def test_start_task_uses_task_id_as_thread_id(self, service, mock_graph, mock_task_store):
        """测试使用 task_id 作为 thread_id"""
        _setup_graph_mocks(mock_graph, GraphInterrupt("outline_confirmation"))

        result = await service.start_task(topic="测试")

        # 中断任务保留在 _tasks 中，thread_id 等于 task_id
        task = service._tasks[result.task_id]
        assert task["thread_id"] == result.task_id


# ============================================
# resume_task 测试
# ============================================


class TestResumeTask:
    """测试任务恢复（HITL）"""

    @pytest.mark.asyncio
    async def test_resume_confirm_outline(self, service, mock_graph):
        """测试确认大纲后恢复执行"""
        _setup_graph_mocks(mock_graph, GraphInterrupt("outline_confirmation"))

        create_result = await service.start_task(topic="测试")
        assert create_result.status == "interrupted"

        _setup_graph_mocks(mock_graph, {"final_draft": "最终文章"})
        resume_result = await service.resume_task(
            task_id=create_result.task_id,
            action="confirm_outline",
        )

        assert resume_result.status == "completed"

    @pytest.mark.asyncio
    async def test_resume_update_outline(self, service, mock_graph):
        """测试更新大纲后恢复执行"""
        _setup_graph_mocks(mock_graph, GraphInterrupt("outline_confirmation"))

        create_result = await service.start_task(topic="测试")

        _setup_graph_mocks(mock_graph, {"final_draft": "更新后的文章"})

        new_outline = [
            {"title": "新章节1", "summary": "内容1"},
            {"title": "新章节2", "summary": "内容2"},
        ]
        resume_result = await service.resume_task(
            task_id=create_result.task_id,
            action="update_outline",
            data={"outline": new_outline },
        )

        assert resume_result.status == "completed"
        mock_graph.aupdate_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_nonexistent_task_raises(self, service):
        """测试恢复不存在的任务抛出 TaskNotFoundError"""
        with pytest.raises(TaskNotFoundError):
            await service.resume_task(task_id="nonexistent", action="confirm_outline")

    @pytest.mark.asyncio
    async def test_resume_graph_error_raises(self, service, mock_graph):
        """测试恢复时图执行错误抛出 GraphExecutionError"""
        _setup_graph_mocks(mock_graph, GraphInterrupt("outline_confirmation"))
        create_result = await service.start_task(topic="测试")

        _setup_graph_mocks(mock_graph, RuntimeError("执行失败"))

        with pytest.raises(GraphExecutionError):
            await service.resume_task(
                task_id=create_result.task_id,
                action="confirm_outline",
            )

    @pytest.mark.asyncio
    async def test_resume_second_interrupt(self, service, mock_graph, mock_task_store):
        """测试恢复后再次中断的处理"""
        _setup_graph_mocks(mock_graph, GraphInterrupt("outline_confirmation"))
        create_result = await service.start_task(topic="测试")

        # 重置 mock 以区分 start 和 resume 的调用
        mock_task_store.save_task.reset_mock()

        _setup_graph_mocks(mock_graph, GraphInterrupt("second_interrupt"))
        resume_result = await service.resume_task(
            task_id=create_result.task_id,
            action="confirm_outline",
        )

        assert resume_result.status == "interrupted"

        # 再次中断应重新持久化
        mock_task_store.save_task.assert_called_once()
        saved_data = mock_task_store.save_task.call_args[0][0]
        assert saved_data["status"] == "interrupted"


# ============================================
# get_task_status 测试
# ============================================


class TestGetTaskStatus:
    """测试任务状态查询"""

    @pytest.mark.asyncio
    async def test_get_status_running_task(self, service, mock_graph):
        """测试查询中断任务的状态（中断任务保留在内存中）"""
        _setup_graph_mocks(mock_graph, GraphInterrupt("outline_confirmation"))

        create_result = await service.start_task(topic="测试")
        status = await service.get_task_status(task_id=create_result.task_id)

        assert isinstance(status, TaskStatusResponse)
        assert status.task_id == create_result.task_id
        assert status.status == "interrupted"

    @pytest.mark.asyncio
    async def test_get_status_interrupted_task(self, service, mock_graph):
        """测试查询中断任务的状态"""
        _setup_graph_mocks(mock_graph, GraphInterrupt("outline_confirmation"))

        create_result = await service.start_task(topic="测试")
        status = await service.get_task_status(task_id=create_result.task_id)

        assert status.status == "interrupted"
        assert status.awaiting == "outline_confirmation"

    @pytest.mark.asyncio
    async def test_get_status_completed_task_with_result(self, service, mock_graph, mock_task_store):
        """测试查询已完成任务的状态包含结果（从 TaskStore 查询）"""
        _setup_graph_mocks(
            mock_graph,
            {"final_draft": "最终文章内容", "current_node": "reducer"},
        )

        create_result = await service.start_task(topic="测试")

        # 已完成任务已从 _tasks 移除，通过 TaskStore 查询
        mock_task_store.get_task.return_value = {
            "task_id": create_result.task_id,
            "graph_type": "creation",
            "status": "completed",
            "topic": "测试",
            "result": "最终文章内容",
            "progress": 100.0,
            "created_at": "2026-05-06T10:00:00",
            "updated_at": "2026-05-06T10:01:00",
        }
        status = await service.get_task_status(task_id=create_result.task_id)

        assert status.status == "completed"
        assert status.result == "最终文章内容"
        assert status.progress == 100.0

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_raises(self, service):
        """测试查询不存在的任务抛出 TaskNotFoundError"""
        with pytest.raises(TaskNotFoundError):
            await service.get_task_status(task_id="nonexistent")

    @pytest.mark.asyncio
    async def test_get_status_with_state(self, service, mock_graph):
        """测试查询中断任务包含完整状态"""
        state_values = {
            "topic": "测试",
            "current_node": "outline_confirmation",
            "outline": [],
            "sections": [],
            "messages": [],
        }
        _setup_graph_mocks(mock_graph, GraphInterrupt("outline_confirmation"), state_values=state_values)

        create_result = await service.start_task(topic="测试")
        status = await service.get_task_status(
            task_id=create_result.task_id,
            include_state=True,
        )

        assert status.state is not None
        assert status.state["topic"] == "测试"

    @pytest.mark.asyncio
    async def test_get_status_with_history(self, service, mock_graph):
        """测试查询中断任务包含执行历史"""
        _setup_graph_mocks(mock_graph, GraphInterrupt("outline_confirmation"))

        mock_checkpoint = MagicMock()
        mock_checkpoint.id = "cp_001"
        mock_checkpoint.ts = "2026-05-03T10:00:00"

        async def mock_alist(config):
            yield mock_checkpoint

        service.checkpointer.alist = mock_alist

        create_result = await service.start_task(topic="测试")
        status = await service.get_task_status(
            task_id=create_result.task_id,
            include_history=True,
        )

        assert status.history is not None
        assert len(status.history) == 1
        assert status.history[0]["checkpoint_id"] == "cp_001"


# ============================================
# 进度计算测试
# ============================================


class TestProgressCalculation:
    """测试进度计算逻辑"""

    def test_progress_completed(self):
        """测试已完成任务进度为 100%"""
        assert CreationService._calculate_progress({}, "completed") == 100.0

    def test_progress_failed(self):
        """测试失败任务进度为 0%"""
        assert CreationService._calculate_progress({}, "failed") == 0.0

    def test_progress_by_node(self):
        """测试各节点的进度值"""
        nodes = {
            "planner": 20.0,
            "outline_confirmation": 30.0,
            "writer": 60.0,
            "reducer": 80.0,
        }
        for node, expected in nodes.items():
            assert CreationService._calculate_progress(
                {"current_node": node}, "running"
            ) == expected

    def test_progress_unknown_node(self):
        """测试未知节点返回默认进度"""
        assert CreationService._calculate_progress(
            {"current_node": "unknown"}, "running"
        ) == 10.0
