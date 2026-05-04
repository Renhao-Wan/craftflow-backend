"""FastAPI 路由层模块

提供 RESTful API 接口，负责请求解析和响应封装。
通过依赖注入调用服务层执行业务逻辑。
"""

from app.api.dependencies import (
    close_services,
    get_creation_service,
    get_polishing_service,
    init_services,
)
from app.api.v1.router import router as v1_router

__all__ = [
    "init_services",
    "close_services",
    "get_creation_service",
    "get_polishing_service",
    "v1_router",
]
