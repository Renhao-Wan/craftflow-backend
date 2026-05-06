"""Polishing 业务服务层测试

测试 PolishingService 的任务创建和状态查询逻辑。
使用 mock 隔离 Graph 执行和 Checkpointer。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import GraphExecutionError, TaskNotFoundError
from app.schemas.response import TaskResponse, TaskStatusResponse
from app.services.polishing_svc import PolishingService


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
    return graph


@pytest.fixture
def service(mock_checkpointer, mock_task_store, mock_graph):
    """创建 PolishingService 实例（注入 mock graph）"""
    svc = PolishingService(checkpointer=mock_checkpointer, task_store=mock_task_store)
    svc._graph = mock_graph
    return svc


def _setup_graph_mocks(mock_graph, invoke_result, state_values=None):
    """统一设置 ainvoke 和 aget_state 的返回值"""
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
    async def test_start_mode1_formatter(self, service, mock_graph):
        """测试 Mode 1 极速格式化"""
        _setup_graph_mocks(mock_graph, {
            "formatted_content": "# 格式化内容",
            "final_content": "# 格式化内容",
            "current_node": "formatter",
        })

        result = await service.start_task(content="# 原始内容\n\n正文", mode=1)

        assert isinstance(result, TaskResponse)
        assert result.task_id.startswith("polishing_")
        assert result.status == "completed"
        assert "极速格式化" in result.message

    @pytest.mark.asyncio
    async def test_start_mode2_debate(self, service, mock_graph):
        """测试 Mode 2 专家对抗审查"""
        _setup_graph_mocks(mock_graph, {
            "final_content": "对抗审查后的内容",
            "overall_score": 95,
            "current_node": "debate",
        })

        result = await service.start_task(content="# 测试内容\n\n正文", mode=2)

        assert result.status == "completed"
        assert "专家对抗审查" in result.message

    @pytest.mark.asyncio
    async def test_start_mode3_fact_checker(self, service, mock_graph):
        """测试 Mode 3 事实核查"""
        _setup_graph_mocks(mock_graph, {
            "fact_check_result": "事实核查完成，准确性: high",
            "current_node": "fact_checker",
        })

        result = await service.start_task(content="# 测试内容\n\n正文", mode=3)

        assert result.status == "completed"
        assert "事实核查" in result.message

    @pytest.mark.asyncio
    async def test_start_task_saves_metadata(self, service, mock_graph, mock_task_store):
        """测试任务元数据正确保存到 TaskStore"""
        _setup_graph_mocks(mock_graph, {"final_content": "结果"})

        content = "测试内容" * 5  # len = 20
        result = await service.start_task(content=content, mode=2)

        # 已完成任务应持久化到 TaskStore 并从 _tasks 移除
        mock_task_store.save_task.assert_called_once()
        saved_data = mock_task_store.save_task.call_args[0][0]
        assert saved_data["status"] == "completed"
        assert saved_data["graph_type"] == "polishing"
        assert saved_data["mode"] == 2
        assert result.task_id not in service._tasks

    @pytest.mark.asyncio
    async def test_start_task_graph_error(self, service, mock_graph):
        """测试图返回错误时抛出异常"""
        _setup_graph_mocks(mock_graph, {"error": "LLM 调用超时"})

        with pytest.raises(GraphExecutionError) as exc_info:
            await service.start_task(content="测试内容" * 5, mode=1)

        assert "LLM 调用超时" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_start_task_exception(self, service, mock_graph, mock_task_store):
        """测试图执行异常时抛出 GraphExecutionError"""
        _setup_graph_mocks(mock_graph, RuntimeError("网络错误"))

        with pytest.raises(GraphExecutionError):
            await service.start_task(content="测试内容" * 5, mode=1)

        # 失败任务应持久化到 TaskStore
        mock_task_store.save_task.assert_called_once()
        saved_data = mock_task_store.save_task.call_args[0][0]
        assert saved_data["status"] == "failed"
        assert "网络错误" in saved_data["error"]

    @pytest.mark.asyncio
    async def test_start_task_passes_correct_state(self, service, mock_graph):
        """测试传递正确的初始状态"""
        _setup_graph_mocks(mock_graph, {})

        content = "# 测试文章\n\n这是正文内容"
        await service.start_task(content=content, mode=2)

        call_args = mock_graph.ainvoke.call_args
        initial_state = call_args[0][0]

        assert initial_state["content"] == content
        assert initial_state["mode"] == 2
        assert initial_state["formatted_content"] is None
        assert initial_state["debate_history"] == []
        assert initial_state["scores"] == []


# ============================================
# get_task_status 测试
# ============================================


class TestGetTaskStatus:
    """测试任务状态查询"""

    @pytest.mark.asyncio
    async def test_get_status_completed_mode1(self, service, mock_graph, mock_task_store):
        """测试 Mode 1 完成后的状态查询（从 TaskStore）"""
        _setup_graph_mocks(mock_graph, {
            "formatted_content": "# 格式化结果",
            "current_node": "formatter",
        })

        create_result = await service.start_task(content="测试内容" * 5, mode=1)

        # 已完成任务从 TaskStore 查询
        mock_task_store.get_task.return_value = {
            "task_id": create_result.task_id,
            "graph_type": "polishing",
            "status": "completed",
            "mode": 1,
            "result": "# 格式化结果",
            "progress": 100.0,
            "created_at": "2026-05-06T10:00:00",
            "updated_at": "2026-05-06T10:01:00",
        }
        status = await service.get_task_status(task_id=create_result.task_id)

        assert isinstance(status, TaskStatusResponse)
        assert status.status == "completed"
        assert status.result == "# 格式化结果"
        assert status.progress == 100.0

    @pytest.mark.asyncio
    async def test_get_status_completed_mode2(self, service, mock_graph, mock_task_store):
        """测试 Mode 2 完成后的状态查询（从 TaskStore）"""
        _setup_graph_mocks(mock_graph, {
            "final_content": "对抗审查结果",
            "overall_score": 92,
            "current_node": "debate",
        })

        create_result = await service.start_task(content="测试内容" * 5, mode=2)

        mock_task_store.get_task.return_value = {
            "task_id": create_result.task_id,
            "graph_type": "polishing",
            "status": "completed",
            "mode": 2,
            "result": "对抗审查结果",
            "progress": 100.0,
            "created_at": "2026-05-06T10:00:00",
            "updated_at": "2026-05-06T10:01:00",
        }
        status = await service.get_task_status(task_id=create_result.task_id)

        assert status.result == "对抗审查结果"

    @pytest.mark.asyncio
    async def test_get_status_completed_mode3(self, service, mock_graph, mock_task_store):
        """测试 Mode 3 完成后的状态查询（从 TaskStore）"""
        _setup_graph_mocks(mock_graph, {
            "fact_check_result": "核查通过",
            "current_node": "fact_checker",
        })

        create_result = await service.start_task(content="测试内容" * 5, mode=3)

        mock_task_store.get_task.return_value = {
            "task_id": create_result.task_id,
            "graph_type": "polishing",
            "status": "completed",
            "mode": 3,
            "result": "核查通过",
            "progress": 100.0,
            "created_at": "2026-05-06T10:00:00",
            "updated_at": "2026-05-06T10:01:00",
        }
        status = await service.get_task_status(task_id=create_result.task_id)

        assert status.result == "核查通过"

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_raises(self, service):
        """测试查询不存在的任务"""
        with pytest.raises(TaskNotFoundError):
            await service.get_task_status(task_id="nonexistent")

    @pytest.mark.asyncio
    async def test_get_status_with_state(self, service, mock_graph, mock_task_store):
        """测试查询已完成任务的完整状态（从 TaskStore，state 为 None）"""
        _setup_graph_mocks(mock_graph, {"final_content": "结果"})

        create_result = await service.start_task(content="测试内容" * 5, mode=2)

        mock_task_store.get_task.return_value = {
            "task_id": create_result.task_id,
            "graph_type": "polishing",
            "status": "completed",
            "mode": 2,
            "result": "结果",
            "progress": 100.0,
            "created_at": "2026-05-06T10:00:00",
            "updated_at": "2026-05-06T10:01:00",
        }
        status = await service.get_task_status(
            task_id=create_result.task_id,
            include_state=True,
        )

        # 已完成任务从 TaskStore 查询，无法读取 checkpoint 状态
        assert status.state is None

    @pytest.mark.asyncio
    async def test_get_status_with_history(self, service, mock_graph, mock_task_store):
        """测试查询已完成任务的执行历史（从 TaskStore，history 为 None）"""
        _setup_graph_mocks(mock_graph, {"final_content": "结果"})

        create_result = await service.start_task(content="测试内容" * 5, mode=1)

        mock_task_store.get_task.return_value = {
            "task_id": create_result.task_id,
            "graph_type": "polishing",
            "status": "completed",
            "mode": 1,
            "result": "结果",
            "progress": 100.0,
            "created_at": "2026-05-06T10:00:00",
            "updated_at": "2026-05-06T10:01:00",
        }
        status = await service.get_task_status(
            task_id=create_result.task_id,
            include_history=True,
        )

        # 已完成任务从 TaskStore 查询，无法读取 checkpoint 历史
        assert status.history is None


# ============================================
# 结果提取测试
# ============================================


class TestExtractResult:
    """测试结果提取逻辑"""

    def test_extract_from_final_content(self):
        """测试从 final_content 提取结果"""
        state = {"final_content": "最终内容", "formatted_content": None}
        assert PolishingService._extract_result(state) == "最终内容"

    def test_extract_from_formatted_content(self):
        """测试从 formatted_content 提取结果"""
        state = {"final_content": None, "formatted_content": "格式化内容"}
        assert PolishingService._extract_result(state) == "格式化内容"

    def test_extract_from_fact_check_result(self):
        """测试从 fact_check_result 提取结果"""
        state = {
            "final_content": None,
            "formatted_content": None,
            "fact_check_result": "核查结果",
        }
        assert PolishingService._extract_result(state) == "核查结果"

    def test_extract_returns_none_when_empty(self):
        """测试无结果时返回 None"""
        state = {
            "final_content": None,
            "formatted_content": None,
            "fact_check_result": None,
        }
        assert PolishingService._extract_result(state) is None


# ============================================
# 进度计算测试
# ============================================


class TestProgressCalculation:
    """测试进度计算逻辑"""

    def test_progress_completed(self):
        assert PolishingService._calculate_progress({}, "completed") == 100.0

    def test_progress_failed(self):
        assert PolishingService._calculate_progress({}, "failed") == 0.0

    def test_progress_by_node(self):
        nodes = {
            "router": 20.0,
            "formatter": 60.0,
            "debate": 60.0,
            "fact_checker": 60.0,
        }
        for node, expected in nodes.items():
            assert PolishingService._calculate_progress(
                {"current_node": node}, "running"
            ) == expected
