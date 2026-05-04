"""WebSocket 消息模型定义

定义所有 WebSocket 通信的消息格式，用于运行时校验和类型提示。
消息通过 JSON 传输，所有模型均支持 `.model_validate()` 解析和 `.model_dump()` 序列化。
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── 客户端 → 服务端 ──────────────────────────────────────


class WsMessage(BaseModel):
    """客户端消息基类"""

    type: str
    request_id: Optional[str] = Field(default=None, alias="requestId")

    model_config = {"populate_by_name": True}


class CreateCreationMessage(WsMessage):
    type: str = "create_creation"
    topic: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=2000)


class CreatePolishingMessage(WsMessage):
    type: str = "create_polishing"
    content: str = Field(..., min_length=10)
    mode: int = Field(default=2, ge=1, le=3)


class ResumeTaskMessage(WsMessage):
    type: str = "resume_task"
    task_id: str = Field(..., alias="taskId")
    action: str
    data: Optional[dict[str, Any]] = None

    model_config = {"populate_by_name": True}


class GetTaskStatusMessage(WsMessage):
    type: str = "get_task_status"
    task_id: str = Field(..., alias="taskId")

    model_config = {"populate_by_name": True}


class SubscribeTaskMessage(WsMessage):
    type: str = "subscribe_task"
    task_id: str = Field(..., alias="taskId")

    model_config = {"populate_by_name": True}


class UnsubscribeTaskMessage(WsMessage):
    type: str = "unsubscribe_task"
    task_id: str = Field(..., alias="taskId")

    model_config = {"populate_by_name": True}


class PingMessage(WsMessage):
    type: str = "ping"


# ── 服务端 → 客户端 ──────────────────────────────────────


class ServerMessage(BaseModel):
    """服务端消息基类"""

    type: str
    request_id: Optional[str] = Field(default=None, alias="requestId", exclude=True)

    def to_dict(self) -> dict[str, Any]:
        """序列化为发送用的 dict（驼峰命名，排除 None）"""
        data = self.model_dump(by_alias=True, exclude_none=True)
        if self.request_id is not None:
            data["requestId"] = self.request_id
        return data


class TaskCreatedMessage(ServerMessage):
    type: str = "task_created"
    task_id: str = Field(..., alias="taskId")
    status: str
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")

    model_config = {"populate_by_name": True}


class TaskUpdateMessage(ServerMessage):
    type: str = "task_update"
    task_id: str = Field(..., alias="taskId")
    status: str
    current_node: Optional[str] = Field(default=None, alias="currentNode")
    progress: Optional[float] = None
    awaiting: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    model_config = {"populate_by_name": True}


class TaskResultMessage(ServerMessage):
    type: str = "task_result"
    task_id: str = Field(..., alias="taskId")
    result: str
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class TaskErrorMessage(ServerMessage):
    type: str = "task_error"
    task_id: str = Field(..., alias="taskId")
    error: str

    model_config = {"populate_by_name": True}


class TaskStatusMessage(ServerMessage):
    """单次查询响应，结构与 TaskStatusResponse 一致"""

    type: str = "task_status"
    task_id: str = Field(..., alias="taskId")
    status: str
    current_node: Optional[str] = Field(default=None, alias="currentNode")
    awaiting: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    result: Optional[str] = None
    error: Optional[str] = None
    progress: Optional[float] = None
    created_at: Optional[datetime] = Field(default=None, alias="createdAt")
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class ErrorMessage(ServerMessage):
    type: str = "error"
    code: str
    message: str


class PongMessage(ServerMessage):
    type: str = "pong"
