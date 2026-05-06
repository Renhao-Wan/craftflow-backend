"""任务 REST API

提供通用的任务查询和删除功能。
- GET    /tasks           任务列表（SQLite 终态 + 内存运行态）
- GET    /tasks/{task_id} 单任务状态查询
- DELETE /tasks/{task_id} 删除任务记录
"""

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import (
    get_creation_service,
    get_polishing_service,
    get_task_store,
)
from app.core.exceptions import TaskNotFoundError
from app.schemas.response import TaskStatusResponse
from app.services.creation_svc import CreationService
from app.services.polishing_svc import PolishingService
from app.services.task_store import TaskStore

router = APIRouter()


@router.get("/tasks")
async def list_tasks(
    limit: int = Query(50, ge=1, le=200, description="最大返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    store: TaskStore = Depends(get_task_store),
    creation_svc: CreationService = Depends(get_creation_service),
    polishing_svc: PolishingService = Depends(get_polishing_service),
) -> list[dict[str, Any]]:
    """获取任务列表

    返回所有任务（包括运行中和已完成的），按创建时间降序排列。
    - running/interrupted 任务从内存 _tasks dict 获取
    - completed/failed 任务从 SQLite 获取
    """
    # 1. 从 SQLite 查询终态任务
    db_tasks = await store.get_task_list(limit=limit, offset=offset)

    # 2. 从内存获取运行中的任务
    running_tasks: list[dict[str, Any]] = []
    for task in creation_svc._tasks.values():
        if task["status"] in ("running", "interrupted"):
            running_tasks.append(_format_running_task(task))
    for task in polishing_svc._tasks.values():
        if task["status"] in ("running", "interrupted"):
            running_tasks.append(_format_running_task(task))

    # 3. 合并并按 created_at 降序排序
    all_tasks = running_tasks + db_tasks
    all_tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    return all_tasks[:limit]


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    creation_svc: CreationService = Depends(get_creation_service),
    polishing_svc: PolishingService = Depends(get_polishing_service),
) -> TaskStatusResponse:
    """查询单个任务状态

    自动识别任务类型（创作/润色），查询顺序：
    1. CreationService（内存 → TaskStore）
    2. PolishingService（内存 → TaskStore）
    """
    try:
        return await creation_svc.get_task_status(task_id)
    except TaskNotFoundError:
        pass

    try:
        return await polishing_svc.get_task_status(task_id)
    except TaskNotFoundError:
        pass

    raise TaskNotFoundError(task_id=task_id)


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    store: TaskStore = Depends(get_task_store),
    creation_svc: CreationService = Depends(get_creation_service),
    polishing_svc: PolishingService = Depends(get_polishing_service),
) -> dict[str, Any]:
    """删除任务记录

    优先从内存中删除运行中的任务，如果内存中没有则从 SQLite 删除。
    """
    # 1. 先检查内存中是否有该任务（running/interrupted）
    if task_id in creation_svc._tasks:
        creation_svc._tasks.pop(task_id, None)
        return {"task_id": task_id, "deleted": True}

    if task_id in polishing_svc._tasks:
        polishing_svc._tasks.pop(task_id, None)
        return {"task_id": task_id, "deleted": True}

    # 2. 内存中没有，从 SQLite 删除
    deleted = await store.delete_task(task_id)
    if not deleted:
        raise TaskNotFoundError(task_id=task_id)
    return {"task_id": task_id, "deleted": True}


def _format_running_task(task: dict[str, Any]) -> dict[str, Any]:
    """将内存中的运行态任务格式化为 API 响应格式"""
    request = task.get("request", {})
    graph_type = task.get("graph_type", "creation")

    result: dict[str, Any] = {
        "task_id": task["task_id"],
        "graph_type": graph_type,
        "status": task["status"],
        "created_at": str(task["created_at"]),
        "updated_at": str(task["updated_at"]),
    }

    if graph_type == "creation":
        result["topic"] = request.get("topic")
        result["description"] = request.get("description")
    elif graph_type == "polishing":
        result["mode"] = request.get("mode")

    return result
