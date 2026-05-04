"""Creation API 端到端测试

测试 Creation 相关的 RESTful 接口。
使用 httpx.AsyncClient 测试完整的请求-响应流程，
mock 服务层以隔离 Graph 执行。
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from httpx import AsyncClient, ASGITransport

from app.api.dependencies import get_creation_service
from app.api.v1.creation import router as creation_router
from app.schemas.response import TaskResponse, TaskStatusResponse
from app.services.creation_svc import CreationService


@pytest.fixture
def mock_service():
    """创建 mock CreationService"""
    return AsyncMock(spec=CreationService)


@pytest.fixture
def app(mock_service):
    """创建测试用 FastAPI 应用，全局覆盖 CreationService 依赖"""
    from fastapi import FastAPI
    from app.core.exceptions import register_exception_handlers

    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(creation_router, prefix="/api/v1")
    application.dependency_overrides[get_creation_service] = lambda: mock_service
    return application


@pytest.fixture
async def client(app):
    """创建测试用 HTTP 客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================
# POST /api/v1/creation 测试
# ============================================


class TestCreateCreationTask:
    """测试创建创作任务"""

    @pytest.mark.asyncio
    async def test_create_task_success(self, client, mock_service):
        """测试成功创建任务"""
        mock_service.start_task.return_value = TaskResponse(
            task_id="creation_abc123",
            status="interrupted",
            message="大纲已生成，请确认后继续",
            created_at=datetime(2026, 5, 4, 10, 0, 0),
        )

        response = await client.post(
            "/api/v1/creation",
            json={"topic": "微服务架构演进", "description": "深入分析"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == "creation_abc123"
        assert data["status"] == "interrupted"
        mock_service.start_task.assert_called_once_with(
            topic="微服务架构演进",
            description="深入分析",
        )

    @pytest.mark.asyncio
    async def test_create_task_minimal(self, client, mock_service):
        """测试最小参数创建任务"""
        mock_service.start_task.return_value = TaskResponse(
            task_id="creation_min",
            status="interrupted",
        )

        response = await client.post(
            "/api/v1/creation",
            json={"topic": "Python 编程"},
        )

        assert response.status_code == 201
        mock_service.start_task.assert_called_once_with(
            topic="Python 编程",
            description="",
        )

    @pytest.mark.asyncio
    async def test_create_task_empty_topic(self, client):
        """测试空主题返回 422"""
        response = await client.post(
            "/api/v1/creation",
            json={"topic": ""},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_task_whitespace_topic(self, client):
        """测试空白主题返回 422"""
        response = await client.post(
            "/api/v1/creation",
            json={"topic": "   "},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_task_missing_topic(self, client):
        """测试缺少主题返回 422"""
        response = await client.post(
            "/api/v1/creation",
            json={},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_task_service_error(self, client, mock_service):
        """测试服务层错误返回 500"""
        from app.core.exceptions import GraphExecutionError

        mock_service.start_task.side_effect = GraphExecutionError(
            message="LLM 调用失败",
            details={"task_id": "creation_fail"},
        )

        response = await client.post(
            "/api/v1/creation",
            json={"topic": "测试主题"},
        )

        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "GRAPH_EXECUTION_ERROR"


# ============================================
# GET /api/v1/tasks/{task_id} 测试
# ============================================


class TestGetTaskStatus:
    """测试查询任务状态"""

    @pytest.mark.asyncio
    async def test_get_status_success(self, client, mock_service):
        """测试成功查询任务状态"""
        mock_service.get_task_status.return_value = TaskStatusResponse(
            task_id="creation_abc123",
            status="interrupted",
            current_node="outline_confirmation",
            awaiting="outline_confirmation",
            progress=30.0,
            created_at=datetime(2026, 5, 4, 10, 0, 0),
            updated_at=datetime(2026, 5, 4, 10, 1, 0),
        )

        response = await client.get("/api/v1/tasks/creation_abc123")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "creation_abc123"
        assert data["status"] == "interrupted"
        assert data["awaiting"] == "outline_confirmation"

    @pytest.mark.asyncio
    async def test_get_status_with_state(self, client, mock_service):
        """测试查询包含完整状态"""
        mock_service.get_task_status.return_value = TaskStatusResponse(
            task_id="creation_abc123",
            status="completed",
            state={"topic": "测试", "outline": []},
        )

        response = await client.get(
            "/api/v1/tasks/creation_abc123",
            params={"include_state": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["state"] is not None

    @pytest.mark.asyncio
    async def test_get_status_with_history(self, client, mock_service):
        """测试查询包含执行历史"""
        mock_service.get_task_status.return_value = TaskStatusResponse(
            task_id="creation_abc123",
            status="completed",
            history=[{"checkpoint_id": "cp_001", "ts": "2026-05-04T10:00:00"}],
        )

        response = await client.get(
            "/api/v1/tasks/creation_abc123",
            params={"include_history": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["history"] is not None
        assert len(data["history"]) == 1

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, client, mock_service):
        """测试查询不存在的任务返回 404"""
        from app.core.exceptions import TaskNotFoundError

        mock_service.get_task_status.side_effect = TaskNotFoundError(task_id="nonexistent")

        response = await client.get("/api/v1/tasks/nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "TASK_NOT_FOUND"


# ============================================
# POST /api/v1/tasks/{task_id}/resume 测试
# ============================================


class TestResumeTask:
    """测试恢复中断的任务"""

    @pytest.mark.asyncio
    async def test_resume_confirm_outline(self, client, mock_service):
        """测试确认大纲后恢复"""
        mock_service.resume_task.return_value = TaskResponse(
            task_id="creation_abc123",
            status="completed",
            message="创作任务已完成",
        )

        response = await client.post(
            "/api/v1/tasks/creation_abc123/resume",
            json={"action": "confirm_outline"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        mock_service.resume_task.assert_called_once_with(
            task_id="creation_abc123",
            action="confirm_outline",
            data=None,
        )

    @pytest.mark.asyncio
    async def test_resume_update_outline(self, client, mock_service):
        """测试更新大纲后恢复"""
        mock_service.resume_task.return_value = TaskResponse(
            task_id="creation_abc123",
            status="completed",
        )

        new_outline = [
            {"title": "新章节1", "summary": "内容1"},
            {"title": "新章节2", "summary": "内容2"},
        ]

        response = await client.post(
            "/api/v1/tasks/creation_abc123/resume",
            json={"action": "update_outline", "data": {"outline": new_outline}},
        )

        assert response.status_code == 200
        mock_service.resume_task.assert_called_once_with(
            task_id="creation_abc123",
            action="update_outline",
            data={"outline": new_outline },
        )

    @pytest.mark.asyncio
    async def test_resume_invalid_action(self, client):
        """测试无效动作返回 422"""
        response = await client.post(
            "/api/v1/tasks/creation_abc123/resume",
            json={"action": "invalid_action"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_resume_missing_action(self, client):
        """测试缺少动作返回 422"""
        response = await client.post(
            "/api/v1/tasks/creation_abc123/resume",
            json={},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_resume_task_not_found(self, client, mock_service):
        """测试恢复不存在的任务返回 404"""
        from app.core.exceptions import TaskNotFoundError

        mock_service.resume_task.side_effect = TaskNotFoundError(task_id="nonexistent")

        response = await client.post(
            "/api/v1/tasks/nonexistent/resume",
            json={"action": "confirm_outline"},
        )

        assert response.status_code == 404
