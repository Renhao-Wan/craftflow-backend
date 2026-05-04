"""Creation API 路由

提供创作任务相关的 RESTful 接口：
- POST   /creation           创建创作任务
- GET    /tasks/{task_id}    查询任务状态
- POST   /tasks/{task_id}/resume  恢复中断的任务（HITL）
"""

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_creation_service
from app.schemas.request import CreationRequest, ResumeRequest
from app.schemas.response import ResumeResponse, TaskResponse, TaskStatusResponse
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


@router.get(
    "/tasks/{task_id}",
    response_model=TaskStatusResponse,
    summary="查询任务状态",
    description="根据任务 ID 查询创作任务的当前状态、进度和结果。",
    responses={
        200: {"description": "查询成功"},
        404: {"description": "任务不存在"},
    },
)
async def get_task_status(
    task_id: str,
    include_state: bool = Query(False, description="是否返回完整图状态"),
    include_history: bool = Query(False, description="是否返回执行历史"),
    service: CreationService = Depends(get_creation_service),
) -> TaskStatusResponse:
    """查询创作任务状态"""
    return await service.get_task_status(
        task_id=task_id,
        include_state=include_state,
        include_history=include_history,
    )


@router.post(
    "/tasks/{task_id}/resume",
    response_model=ResumeResponse,
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
) -> ResumeResponse:
    """恢复被中断的创作任务

    支持的动作：
    - confirm_outline: 确认当前大纲，继续执行
    - update_outline: 更新大纲后继续执行（需在 data 中提供新大纲）
    """
    result = await service.resume_task(
        task_id=task_id,
        action=request.action,
        data=request.data,
    )

    return ResumeResponse(
        task_id=result.task_id,
        status=result.status,
        message=result.message or "任务已恢复执行",
    )
