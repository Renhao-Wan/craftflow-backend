"""Creation API 路由

提供创作任务相关的 RESTful 接口：
- POST   /creation                  创建创作任务
- POST   /tasks/{task_id}/resume    恢复中断的任务（HITL）
"""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_creation_service
from app.schemas.request import CreationRequest, ResumeRequest
from app.schemas.response import TaskResponse
from app.services.creation_svc import CreationService

router = APIRouter()


@router.post(
    "/creation",
    response_model=TaskResponse,
    status_code=201,
    summary="创建创作任务",
    description="发起一个创作流程。系统将生成大纲并在大纲确认点暂停，等待用户确认。",
    responses={
        201: {"description": "任务创建成功"},
        422: {"description": "请求参数验证失败"},
        500: {"description": "服务内部错误"},
    },
)
async def create_creation_task(
    request: CreationRequest,
    service: CreationService = Depends(get_creation_service),
) -> TaskResponse:
    """创建创作任务

    调用 Creation Graph 执行 PlannerNode 生成大纲后，
    在 outline_confirmation 中断点暂停。
    """
    return await service.start_task(
        topic=request.topic,
        description=request.description,
    )


@router.post(
    "/tasks/{task_id}/resume",
    response_model=TaskResponse,
    summary="恢复中断的任务",
    description="在 HITL 中断点（大纲确认）恢复任务执行。支持确认或更新大纲。",
    responses={
        200: {"description": "任务恢复成功"},
        404: {"description": "任务不存在"},
        422: {"description": "请求参数验证失败"},
        500: {"description": "服务内部错误"},
    },
)
async def resume_task(
    task_id: str,
    request: ResumeRequest,
    service: CreationService = Depends(get_creation_service),
) -> TaskResponse:
    """恢复被中断的创作任务

    支持的动作：
    - confirm_outline: 确认当前大纲，继续执行
    - update_outline: 更新大纲后继续执行（需在 data 中提供新大纲）
    """
    return await service.resume_task(
        task_id=task_id,
        action=request.action,
        data=request.data,
    )
