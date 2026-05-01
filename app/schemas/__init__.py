"""
数据传输对象 (DTO) 模块

本模块导出所有 API 请求和响应模型，供路由层使用。
"""

from app.schemas.request import (
    CreationRequest,
    PolishingRequest,
    ResumeRequest,
    TaskQueryParams,
)

from app.schemas.response import (
    TaskResponse,
    TaskStatusResponse,
    ErrorResponse,
    ResumeResponse,
    HealthResponse,
)

__all__ = [
    # 请求模型
    "CreationRequest",
    "PolishingRequest",
    "ResumeRequest",
    "TaskQueryParams",
    # 响应模型
    "TaskResponse",
    "TaskStatusResponse",
    "ErrorResponse",
    "ResumeResponse",
    "HealthResponse",
]
