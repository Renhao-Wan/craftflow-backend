"""API v1 路由聚合

将 v1 版本的所有路由模块聚合到一个统一的 APIRouter 中。
在 app/main.py 中通过 include_router 注册到 FastAPI 应用。
"""

from fastapi import APIRouter

from app.api.v1.creation import router as creation_router
from app.api.v1.polishing import router as polishing_router

router = APIRouter(prefix="/api/v1")

router.include_router(creation_router, tags=["Creation"])
router.include_router(polishing_router, tags=["Polishing"])
