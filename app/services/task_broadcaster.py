"""任务广播服务

管理 WebSocket 连接的订阅关系，在任务状态变更时向订阅者推送消息。
"""

import json
from typing import Any

from fastapi import WebSocket

from app.core.logger import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """WebSocket 连接管理器

    管理所有活跃的 WebSocket 连接，提供发送/广播能力。
    """

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[client_id] = websocket
        logger.info(f"WebSocket 连接建立 - client_id: {client_id}")

    def disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)
        logger.info(f"WebSocket 连接断开 - client_id: {client_id}")

    def is_connected(self, client_id: str) -> bool:
        return client_id in self._connections

    async def send_to(self, client_id: str, message: dict[str, Any]) -> bool:
        """向指定客户端发送消息，返回是否成功"""
        ws = self._connections.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send_text(json.dumps(message, ensure_ascii=False, default=str))
            return True
        except Exception as e:
            logger.warning(f"发送消息失败 - client_id: {client_id}, error: {e}")
            self.disconnect(client_id)
            return False

    async def broadcast(self, message: dict[str, Any]) -> None:
        """向所有连接广播消息"""
        dead: list[str] = []
        for client_id, ws in self._connections.items():
            try:
                await ws.send_text(json.dumps(message, ensure_ascii=False, default=str))
            except Exception:
                dead.append(client_id)
        for client_id in dead:
            self.disconnect(client_id)

    @property
    def active_count(self) -> int:
        return len(self._connections)


class TaskBroadcaster:
    """任务广播服务

    管理任务与客户端的订阅关系，状态变更时向订阅者推送。
    """

    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager
        self._subscribers: dict[str, set[str]] = {}  # task_id -> {client_ids}

    def subscribe(self, client_id: str, task_id: str) -> None:
        if task_id not in self._subscribers:
            self._subscribers[task_id] = set()
        self._subscribers[task_id].add(client_id)
        logger.debug(f"订阅 - client: {client_id}, task: {task_id}")

    def unsubscribe(self, client_id: str, task_id: str) -> None:
        subs = self._subscribers.get(task_id)
        if subs:
            subs.discard(client_id)
            if not subs:
                del self._subscribers[task_id]
        logger.debug(f"取消订阅 - client: {client_id}, task: {task_id}")

    def remove_client(self, client_id: str) -> None:
        """清理断开连接客户端的所有订阅"""
        empty_tasks: list[str] = []
        for task_id, subs in self._subscribers.items():
            subs.discard(client_id)
            if not subs:
                empty_tasks.append(task_id)
        for task_id in empty_tasks:
            del self._subscribers[task_id]

    def get_subscribers(self, task_id: str) -> set[str]:
        return self._subscribers.get(task_id, set()).copy()

    async def send_to(self, client_id: str, message: dict[str, Any]) -> bool:
        """向指定客户端发送消息"""
        return await self._manager.send_to(client_id, message)

    async def broadcast_update(self, task_id: str, update: dict[str, Any]) -> None:
        """向任务订阅者广播状态更新"""
        message = {"type": "task_update", "taskId": task_id, **update}
        await self._send_to_subscribers(task_id, message)

    async def broadcast_result(
        self,
        task_id: str,
        result: str,
        created_at: Any = None,
        updated_at: Any = None,
    ) -> None:
        """广播任务完成"""
        message: dict[str, Any] = {
            "type": "task_result",
            "taskId": task_id,
            "result": result,
        }
        if created_at:
            message["createdAt"] = str(created_at)
        if updated_at:
            message["updatedAt"] = str(updated_at)
        await self._send_to_subscribers(task_id, message)

    async def broadcast_error(self, task_id: str, error: str) -> None:
        """广播任务失败"""
        message = {"type": "task_error", "taskId": task_id, "error": error}
        await self._send_to_subscribers(task_id, message)

    async def _send_to_subscribers(self, task_id: str, message: dict[str, Any]) -> None:
        subs = self._subscribers.get(task_id)
        if not subs:
            return
        dead: list[str] = []
        for client_id in subs.copy():
            ok = await self._manager.send_to(client_id, message)
            if not ok:
                dead.append(client_id)
        for client_id in dead:
            subs.discard(client_id)
