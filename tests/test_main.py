"""应用入口测试

测试 FastAPI 应用的创建、中间件、异常处理器、路由注册和生命周期。
"""

import pytest
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    """创建测试用 FastAPI 应用"""
    return create_app()


@pytest.fixture
async def client(app):
    """创建测试用 HTTP 客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ============================================
# 应用实例测试
# ============================================


class TestAppCreation:
    """测试应用实例创建"""

    def test_app_instance(self, app):
        """测试 create_app 返回 FastAPI 实例"""
        from fastapi import FastAPI

        assert isinstance(app, FastAPI)

    def test_app_metadata(self, app):
        """测试应用元数据"""
        assert app.title == "CraftFlow Backend"
        assert app.version == "0.1.0"
        assert "LangGraph" in app.description

    def test_routes_registered(self, app):
        """测试路由是否注册"""
        routes = [r.path for r in app.routes if hasattr(r, "path")]
        assert "/health" in routes
        assert "/api/v1/creation" in routes
        assert "/api/v1/polishing" in routes
        assert "/api/v1/tasks/{task_id}" in routes


# ============================================
# 健康检查端点测试
# ============================================


class TestHealthCheck:
    """测试健康检查端点"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """测试 GET /health 返回 200"""
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "environment" in data


# ============================================
# CORS 中间件测试
# ============================================


class TestCORSMiddleware:
    """测试 CORS 中间件"""

    @pytest.mark.asyncio
    async def test_cors_preflight(self, client):
        """测试 CORS 预检请求"""
        response = await client.options(
            "/api/v1/creation",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers

    @pytest.mark.asyncio
    async def test_cors_headers_on_get(self, client):
        """测试 GET 请求包含 CORS 头"""
        response = await client.get(
            "/health",
            headers={"Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


# ============================================
# 异常处理器测试
# ============================================


class TestExceptionHandlers:
    """测试全局异常处理器注册"""

    def test_exception_handlers_registered(self, app):
        """测试异常处理器是否注册"""
        # FastAPI 的 exception_handlers 是一个字典
        handlers = app.exception_handlers
        # 应该包含 CraftFlowException、RequestValidationError、Exception 的处理器
        assert len(handlers) >= 2  # 至少有 validation 和 generic handler


# ============================================
# 生命周期测试
# ============================================


class TestLifespan:
    """测试应用生命周期"""

    @pytest.mark.asyncio
    async def test_startup_calls_init(self, app):
        """测试 startup 事件调用初始化函数"""
        with (
            patch("app.main.init_checkpointer", new_callable=AsyncMock) as mock_cp,
            patch("app.main.init_services", new_callable=AsyncMock) as mock_svc,
            patch("app.main.setup_logger") as mock_logger,
        ):
            # 触发 lifespan startup
            async with app.router.lifespan_context(app):
                mock_logger.assert_called_once()
                mock_cp.assert_awaited_once()
                mock_svc.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_shutdown_calls_close(self, app):
        """测试 shutdown 事件调用关闭函数"""
        with (
            patch("app.main.init_checkpointer", new_callable=AsyncMock),
            patch("app.main.init_services", new_callable=AsyncMock),
            patch("app.main.setup_logger"),
            patch("app.main.close_services", new_callable=AsyncMock) as mock_close_svc,
            patch(
                "app.main.close_checkpointer", new_callable=AsyncMock
            ) as mock_close_cp,
        ):
            # 触发 lifespan startup + shutdown
            async with app.router.lifespan_context(app):
                pass
            mock_close_svc.assert_awaited_once()
            mock_close_cp.assert_awaited_once()
