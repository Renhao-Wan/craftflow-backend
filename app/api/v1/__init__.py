"""API v1 版本路由

聚合 Creation 和 Polishing 路由，统一挂载到 /api/v1 前缀下。
"""

from app.api.v1.router import router

__all__ = ["router"]
