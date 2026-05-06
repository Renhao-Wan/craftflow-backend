"""WebSocket 消息处理逻辑

解析客户端消息，路由到对应的 service 方法，构造响应。
与 ws.py（连接管理/端点）分离，保持职责单一。
"""

import asyncio
import json
from typing import Any

from app.api.dependencies import get_creation_service, get_polishing_service, get_task_store
from app.core.logger import get_logger
from app.schemas.ws_message import (
    CreateCreationMessage,
    CreatePolishingMessage,
    GetTaskStatusMessage,
    ResumeTaskMessage,
    SubscribeTaskMessage,
    UnsubscribeTaskMessage,
)
from app.services.task_broadcaster import TaskBroadcaster

logger = get_logger(__name__)


async def handle_message(
    raw: dict[str, Any],
    client_id: str,
    broadcaster: TaskBroadcaster,
) -> None:
    """处理一条客户端 WebSocket 消息

    Args:
        raw: 解析后的 JSON dict
        client_id: 发送方客户端 ID
        broadcaster: 任务广播服务
    """
    msg_type = raw.get("type", "")
    request_id = raw.get("requestId")

    try:
        if msg_type == "ping":
            await broadcaster.send_to(client_id, {"type": "pong"})

        elif msg_type == "create_creation":
            msg = CreateCreationMessage.model_validate(raw)
            await _handle_create_creation(msg, client_id, broadcaster)

        elif msg_type == "create_polishing":
            msg = CreatePolishingMessage.model_validate(raw)
            await _handle_create_polishing(msg, client_id, broadcaster)

        elif msg_type == "resume_task":
            msg = ResumeTaskMessage.model_validate(raw)
            await _handle_resume_task(msg, client_id, broadcaster)

        elif msg_type == "get_task_status":
            msg = GetTaskStatusMessage.model_validate(raw)
            await _handle_get_task_status(msg, client_id, broadcaster)

        elif msg_type == "subscribe_task":
            msg = SubscribeTaskMessage.model_validate(raw)
            broadcaster.subscribe(client_id, msg.task_id)

        elif msg_type == "unsubscribe_task":
            msg = UnsubscribeTaskMessage.model_validate(raw)
            broadcaster.unsubscribe(client_id, msg.task_id)

        else:
            await broadcaster.send_to(
                client_id,
                {
                    "type": "error",
                    "requestId": request_id,
                    "code": "UNKNOWN_TYPE",
                    "message": f"未知消息类型: {msg_type}",
                },
            )

    except Exception as e:
        logger.error(f"处理消息异常 - type: {msg_type}, client: {client_id}, error: {e}")
        await broadcaster.send_to(
            client_id,
            {
                "type": "error",
                "requestId": request_id,
                "code": "INTERNAL_ERROR",
                "message": str(e),
            },
        )


async def _handle_create_creation(
    msg: CreateCreationMessage,
    client_id: str,
    broadcaster: TaskBroadcaster,
) -> None:
    """处理创作任务创建 — 在后台执行图，实时推送进度"""
    service = get_creation_service()

    # 自动订阅
    # task_id 在 service 内部生成，先启动任务再订阅
    async def _run() -> None:
        try:
            await service.start_task_streaming(
                topic=msg.topic,
                description=msg.description,
                broadcaster=broadcaster,
                client_id=client_id,
                request_id=msg.request_id,
            )
        except Exception as e:
            logger.error(f"创作任务流式执行异常: {e}")

    asyncio.create_task(_run())


async def _handle_create_polishing(
    msg: CreatePolishingMessage,
    client_id: str,
    broadcaster: TaskBroadcaster,
) -> None:
    """处理润色任务创建 — 在后台执行图，实时推送进度"""
    service = get_polishing_service()

    async def _run() -> None:
        try:
            await service.start_task_streaming(
                content=msg.content,
                mode=msg.mode,
                broadcaster=broadcaster,
                client_id=client_id,
                request_id=msg.request_id,
            )
        except Exception as e:
            logger.error(f"润色任务流式执行异常: {e}")

    asyncio.create_task(_run())


async def _handle_resume_task(
    msg: ResumeTaskMessage,
    client_id: str,
    broadcaster: TaskBroadcaster,
) -> None:
    """处理 HITL 恢复 — 在后台执行图恢复，实时推送进度"""
    service = get_creation_service()

    async def _run() -> None:
        try:
            await service.resume_task_streaming(
                task_id=msg.task_id,
                action=msg.action,
                data=msg.data,
                broadcaster=broadcaster,
                client_id=client_id,
                request_id=msg.request_id,
            )
        except Exception as e:
            logger.error(f"恢复任务流式执行异常: {e}")

    asyncio.create_task(_run())


async def _handle_get_task_status(
    msg: GetTaskStatusMessage,
    client_id: str,
    broadcaster: TaskBroadcaster,
) -> None:
    """查询任务状态 — 先查内存，再回退 SQLite"""
    creation_svc = get_creation_service()
    polishing_svc = get_polishing_service()

    try:
        # 先查内存中的 running/interrupted 任务
        status = None
        try:
            status = await creation_svc.get_task_status(msg.task_id)
        except Exception:
            try:
                status = await polishing_svc.get_task_status(msg.task_id)
            except Exception:
                pass

        # 内存未找到，回退查询 SQLite（completed/failed 的终态任务）
        if status is None:
            store = get_task_store()
            row = await store.get_task(msg.task_id)
            if row is None:
                raise Exception(f"任务不存在: {msg.task_id}")

            # 从 SQLite 列重建 data 字段
            data = None
            if row.get("outline"):
                try:
                    data = {"outline": json.loads(row["outline"])}
                except (json.JSONDecodeError, TypeError):
                    pass

            # 将 SQLite 行数据转为与 TaskStatusResponse 兼容的格式
            await broadcaster.send_to(
                client_id,
                {
                    "type": "task_status",
                    "requestId": msg.request_id,
                    "taskId": row["task_id"],
                    "status": row["status"],
                    "currentNode": None,
                    "awaiting": None,
                    "data": data,
                    "result": row.get("result"),
                    "error": row.get("error"),
                    "progress": row.get("progress"),
                    "createdAt": row.get("created_at"),
                    "updatedAt": row.get("updated_at"),
                },
            )
            return

        await broadcaster.send_to(
            client_id,
            {
                "type": "task_status",
                "requestId": msg.request_id,
                "taskId": status.task_id,
                "status": status.status,
                "currentNode": status.current_node,
                "awaiting": status.awaiting,
                "data": status.data,
                "result": status.result,
                "error": status.error,
                "progress": status.progress,
                "createdAt": str(status.created_at) if status.created_at else None,
                "updatedAt": str(status.updated_at) if status.updated_at else None,
            },
        )

    except Exception as e:
        await broadcaster.send_to(
            client_id,
            {
                "type": "error",
                "requestId": msg.request_id,
                "code": "TASK_NOT_FOUND",
                "message": str(e),
            },
        )
