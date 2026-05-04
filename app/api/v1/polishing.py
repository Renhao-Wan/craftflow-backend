"""Polishing API 路由

提供润色任务相关的 RESTful 接口：
- POST /polishing  创建润色任务（三档模式）
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_polishing_service
from app.schemas.request import PolishingRequest
from app.schemas.response import TaskResponse
from app.services.polishing_svc import PolishingService

router = APIRouter()


@router.post(
    "/polishing",
    response_model=TaskResponse,
    status_code=201,
    summary="创建润色任务",
    description=(
        "发起一个润色流程。支持三种模式：\n"
        "- **模式 1**：极速格式化（单次格式整理）\n"
        "- **模式 2**：专家对抗审查（Author-Editor 多轮对抗）\n"
        "- **模式 3**：事实核查（准确性验证）"
    ),
    responses={
        201: {"description": "任务创建成功"},
        422: {"description": "请求参数验证失败"},
        500: {"description": "服务内部错误"},
    },
)
async def create_polishing_task(
    request: PolishingRequest,
    service: PolishingService = Depends(get_polishing_service),
) -> TaskResponse:
    """创建润色任务

    调用 Polishing Graph 执行指定模式的润色流程。
    图执行完成后直接返回结果（无 HITL 中断）。
    """
    return await service.start_task(
        content=request.content,
        mode=request.mode,
    )
