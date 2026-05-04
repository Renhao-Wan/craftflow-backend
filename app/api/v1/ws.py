"""WebSocket 端点

提供 /ws WebSocket 入口，管理连接生命周期，将消息分发给 ws_handler。
"""

import json
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.v1.ws_handler import handle_message
from app.core.logger import get_logger
from app.services.task_broadcaster import ConnectionManager, TaskBroadcaster

logger = get_logger(__name__)

router = APIRouter()

# 模块级单例，在 main.py lifespan 中初始化
_manager: ConnectionManager | None = None
_broadcaster: TaskBroadcaster | None = None


def init_ws_services() -> tuple[ConnectionManager, TaskBroadcaster]:
    """初始化 WebSocket 服务（应用启动时调用）"""
    global _manager, _broadcaster
    _manager = ConnectionManager()
    _broadcaster = TaskBroadcaster(_manager)
    logger.info("WebSocket 服务初始化完成")
    return _manager, _broadcaster


def get_ws_manager() -> ConnectionManager:
    assert _manager is not None, "WebSocket ConnectionManager 尚未初始化"
    return _manager


def get_ws_broadcaster() -> TaskBroadcaster:
    assert _broadcaster is not None, "WebSocket TaskBroadcaster 尚未初始化"
    return _broadcaster


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    """WebSocket 入口

    连接建立后进入消息循环，接收 JSON 消息并分发给 handler。
    连接断开时清理订阅和连接。
    """
    manager = get_ws_manager()
    broadcaster = get_ws_broadcaster()
    client_id = f"ws_{uuid4().hex[:8]}"

    await manager.connect(client_id, websocket)

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                raw = json.loads(raw_text)
            except json.JSONDecodeError:
                await broadcaster.send_to(
                    client_id,
                    {"type": "error", "code": "INVALID_JSON", "message": "无效的 JSON 格式"},
                )
                continue

            await handle_message(raw, client_id, broadcaster)

    except WebSocketDisconnect:
        logger.info(f"客户端主动断开 - client_id: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket 异常 - client_id: {client_id}, error: {e}")
    finally:
        broadcaster.remove_client(client_id)
        manager.disconnect(client_id)
