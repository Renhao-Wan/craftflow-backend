"""Polishing API 端到端测试

测试 Polishing 相关的 RESTful 接口。
使用 httpx.AsyncClient 测试完整的请求-响应流程，
mock 服务层以隔离 Graph 执行。
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from httpx import AsyncClient, ASGITransport

from app.api.dependencies import get_polishing_service
from app.api.v1.polishing import router as polishing_router
from app.schemas.response import TaskResponse
from app.services.polishing_svc import PolishingService


@pytest.fixture
def mock_service():
    """创建 mock PolishingService"""
    return AsyncMock(spec=PolishingService)


@pytest.fixture
def app(mock_service):
    """创建测试用 FastAPI 应用，全局覆盖 PolishingService 依赖"""
    from fastapi import FastAPI
    from app.core.exceptions import register_exception_handlers

    application = FastAPI()
    register_exception_handlers(application)
    application.include_router(polishing_router, prefix="/api/v1")
    application.dependency_overrides[get_polishing_service] = lambda: mock_service
    return application


@pytest.fixture
async def client(app):
    """创建测试用 HTTP 客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


VALID_CONTENT = "# 测试文章\n\n这是正文内容，需要超过十个字符。"


# ============================================
# POST /api/v1/polishing 测试
# ============================================


class TestCreatePolishingTask:
    """测试创建润色任务"""

    @pytest.mark.asyncio
    async def test_create_mode1(self, client, mock_service):
        """测试 Mode 1 极速格式化"""
        mock_service.start_task.return_value = TaskResponse(
            task_id="polishing_001",
            status="completed",
            message="极速格式化完成",
            created_at=datetime(2026, 5, 4, 10, 0, 0),
        )

        response = await client.post(
            "/api/v1/polishing",
            json={"content": VALID_CONTENT, "mode": 1},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == "polishing_001"
        assert data["status"] == "completed"
        mock_service.start_task.assert_called_once_with(
            content=VALID_CONTENT,
            mode=1,
        )

    @pytest.mark.asyncio
    async def test_create_mode2(self, client, mock_service):
        """测试 Mode 2 专家对抗审查"""
        mock_service.start_task.return_value = TaskResponse(
            task_id="polishing_002",
            status="completed",
            message="专家对抗审查完成",
        )

        response = await client.post(
            "/api/v1/polishing",
            json={"content": VALID_CONTENT, "mode": 2},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == "polishing_002"

    @pytest.mark.asyncio
    async def test_create_mode3(self, client, mock_service):
        """测试 Mode 3 事实核查"""
        mock_service.start_task.return_value = TaskResponse(
            task_id="polishing_003",
            status="completed",
            message="事实核查完成",
        )

        response = await client.post(
            "/api/v1/polishing",
            json={"content": VALID_CONTENT, "mode": 3},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["task_id"] == "polishing_003"

    @pytest.mark.asyncio
    async def test_create_default_mode(self, client, mock_service):
        """测试默认模式为 2"""
        mock_service.start_task.return_value = TaskResponse(
            task_id="polishing_default",
            status="completed",
        )

        response = await client.post(
            "/api/v1/polishing",
            json={"content": VALID_CONTENT},
        )

        assert response.status_code == 201
        mock_service.start_task.assert_called_once_with(
            content=VALID_CONTENT,
            mode=2,
        )

    @pytest.mark.asyncio
    async def test_create_content_too_short(self, client):
        """测试内容太短返回 422"""
        response = await client.post(
            "/api/v1/polishing",
            json={"content": "短", "mode": 1},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_empty_content(self, client):
        """测试空内容返回 422"""
        response = await client.post(
            "/api/v1/polishing",
            json={"content": "", "mode": 1},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_invalid_mode(self, client):
        """测试无效模式返回 422"""
        response = await client.post(
            "/api/v1/polishing",
            json={"content": VALID_CONTENT, "mode": 4},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_mode_zero(self, client):
        """测试模式 0 返回 422"""
        response = await client.post(
            "/api/v1/polishing",
            json={"content": VALID_CONTENT, "mode": 0},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_service_error(self, client, mock_service):
        """测试服务层错误返回 500"""
        from app.core.exceptions import GraphExecutionError

        mock_service.start_task.side_effect = GraphExecutionError(
            message="润色执行失败",
            details={"task_id": "polishing_fail", "mode": 2},
        )

        response = await client.post(
            "/api/v1/polishing",
            json={"content": VALID_CONTENT, "mode": 2},
        )

        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "GRAPH_EXECUTION_ERROR"
