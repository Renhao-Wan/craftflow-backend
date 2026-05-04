"""
API 响应模型定义

本模块定义所有 API 接口的响应数据传输对象 (DTO)。
使用 Pydantic 进行数据校验和序列化。
"""

from typing import Optional, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class TaskResponse(BaseModel):
    """
    任务创建响应模型
    
    用于 POST /api/v1/creation 和 POST /api/v1/polishing 接口的响应
    """
    task_id: str = Field(
        ...,
        description="任务唯一标识符（UUID 格式）",
        examples=["c-550e8400-e29b-41d4-a716-446655440000"]
    )
    
    status: Literal["running", "interrupted", "completed", "failed"] = Field(
        ...,
        description="任务状态",
        examples=["running"]
    )
    
    message: Optional[str] = Field(
        default=None,
        description="附加说明信息",
        examples=["任务已成功创建并开始执行"]
    )
    
    created_at: Optional[datetime] = Field(
        default=None,
        description="任务创建时间"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "c-550e8400-e29b-41d4-a716-446655440000",
                "status": "running",
                "message": "任务已成功创建并开始执行",
                "created_at": "2026-05-01T10:30:00Z"
            }
        }


class TaskStatusResponse(BaseModel):
    """
    任务状态查询响应模型
    
    用于 GET /api/v1/tasks/{task_id} 接口的响应
    """
    task_id: str = Field(
        ...,
        description="任务唯一标识符",
        examples=["c-550e8400-e29b-41d4-a716-446655440000"]
    )
    
    status: Literal["running", "interrupted", "completed", "failed"] = Field(
        ...,
        description="任务当前状态",
        examples=["interrupted"]
    )
    
    current_node: Optional[str] = Field(
        default=None,
        description="当前执行的节点名称",
        examples=["PlannerNode"]
    )
    
    awaiting: Optional[str] = Field(
        default=None,
        description="等待的人工操作类型（仅在 interrupted 状态时有值）",
        examples=["outline_confirmation"]
    )
    
    data: Optional[dict[str, Any]] = Field(
        default=None,
        description="当前状态数据（如大纲、草稿等）",
        examples=[{"outline": [{"title": "第一章", "summary": "概述"}]}]
    )
    
    result: Optional[str] = Field(
        default=None,
        description="最终结果（仅在 completed 状态时有值）",
        examples=["# 微服务架构演进\n\n完整的文章内容..."]
    )
    
    error: Optional[str] = Field(
        default=None,
        description="错误信息（仅在 failed 状态时有值）",
        examples=["LLM API 调用超时"]
    )
    
    progress: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="任务进度百分比（0-100）",
        examples=[45.5]
    )
    
    state: Optional[dict[str, Any]] = Field(
        default=None,
        description="完整的图状态数据（仅在请求参数 include_state=true 时返回）"
    )
    
    history: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="执行历史记录（仅在请求参数 include_history=true 时返回）"
    )
    
    created_at: Optional[datetime] = Field(
        default=None,
        description="任务创建时间"
    )
    
    updated_at: Optional[datetime] = Field(
        default=None,
        description="任务最后更新时间"
    )
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "description": "运行中状态",
                    "value": {
                        "task_id": "c-550e8400-e29b-41d4-a716-446655440000",
                        "status": "running",
                        "current_node": "WriterNode",
                        "progress": 45.5,
                        "created_at": "2026-05-01T10:30:00Z",
                        "updated_at": "2026-05-01T10:35:00Z"
                    }
                },
                {
                    "description": "中断等待人工确认",
                    "value": {
                        "task_id": "c-550e8400-e29b-41d4-a716-446655440000",
                        "status": "interrupted",
                        "current_node": "PlannerNode",
                        "awaiting": "outline_confirmation",
                        "data": {
                            "outline": [
                                {"title": "第一章：微服务概述", "summary": "介绍基本概念"},
                                {"title": "第二章：架构演进", "summary": "演进路径分析"}
                            ]
                        },
                        "progress": 20.0,
                        "created_at": "2026-05-01T10:30:00Z",
                        "updated_at": "2026-05-01T10:32:00Z"
                    }
                },
                {
                    "description": "完成状态",
                    "value": {
                        "task_id": "c-550e8400-e29b-41d4-a716-446655440000",
                        "status": "completed",
                        "result": "# 微服务架构演进\n\n完整的文章内容...",
                        "progress": 100.0,
                        "created_at": "2026-05-01T10:30:00Z",
                        "updated_at": "2026-05-01T11:00:00Z"
                    }
                }
            ]
        }


class ErrorResponse(BaseModel):
    """
    错误响应模型
    
    用于所有接口的错误响应
    """
    error: str = Field(
        ...,
        description="错误类型或错误代码",
        examples=["ValidationError"]
    )
    
    message: str = Field(
        ...,
        description="错误详细信息",
        examples=["主题不能为空白字符"]
    )
    
    detail: Optional[dict[str, Any]] = Field(
        default=None,
        description="错误详细信息（可选）",
        examples=[{"field": "topic", "issue": "不能为空"}]
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="错误发生时间"
    )
    
    path: Optional[str] = Field(
        default=None,
        description="请求路径",
        examples=["/api/v1/creation"]
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "主题不能为空白字符",
                "detail": {
                    "field": "topic",
                    "issue": "不能为空"
                },
                "timestamp": "2026-05-01T10:30:00Z",
                "path": "/api/v1/creation"
            }
        }


