"""CraftFlow 应用入口

创建 FastAPI 应用实例，配置中间件、异常处理器和生命周期事件。
启动命令：uv run uvicorn app.main:app --reload --env-file .env.dev --host 127.0.0.1 --port 8000
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import close_services, init_services
from app.api.v1.router import router as v1_router
from app.api.v1.ws import router as ws_router, init_ws_services
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logger import get_logger, setup_logger
from app.services.checkpointer import close_checkpointer, init_checkpointer

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理

    startup: 初始化日志、Checkpointer、业务服务
    shutdown: 关闭业务服务、Checkpointer
    """
    # ── startup ──
    setup_logger()
    logger.info(
        f"CraftFlow 启动中 | 环境: {settings.environment} | "
        f"版本: {settings.app_version}"
    )

    await init_checkpointer()
    await init_services()
    init_ws_services()

    logger.info("CraftFlow 启动完成")

    yield

    # ── shutdown ──
    logger.info("CraftFlow 正在关闭...")
    await close_services()
    await close_checkpointer()
    logger.info("CraftFlow 已关闭")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用实例

    Returns:
        FastAPI: 配置完成的应用实例
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="基于 LangGraph 的智能长文创作与多阶审校平台",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常处理器
    register_exception_handlers(app)

    # v1 路由（REST）
    app.include_router(v1_router)

    # WebSocket 路由
    app.include_router(ws_router)

    # 健康检查
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "version": settings.app_version,
            "environment": settings.environment,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
