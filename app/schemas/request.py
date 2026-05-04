"""
API 请求模型定义

本模块定义所有 API 接口的请求数据传输对象 (DTO)。
使用 Pydantic 进行数据校验和序列化。
"""

from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator


class CreationRequest(BaseModel):
    """
    创作任务请求模型
    
    用于 POST /api/v1/creation 接口
    """
    topic: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="文章主题，必填",
        examples=["微服务架构演进"]
    )
    
    description: Optional[str] = Field(
        default="",
        max_length=2000,
        description="补充描述或需求说明，可选",
        examples=["请重点关注容器化部署和服务治理"]
    )
    
    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        """验证主题不能为空白字符"""
        if not v.strip():
            raise ValueError("主题不能为空白字符")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "topic": "微服务架构演进",
                "description": "请重点关注容器化部署和服务治理"
            }
        }


class PolishingRequest(BaseModel):
    """
    润色任务请求模型
    
    用于 POST /api/v1/polishing 接口
    """
    content: str = Field(
        ...,
        min_length=10,
        description="待润色的文章内容（Markdown 格式）",
        examples=["# 标题\n\n正文内容..."]
    )
    
    mode: int = Field(
        default=2,
        ge=1,
        le=3,
        description="润色模式：1=极速格式化, 2=专家对抗审查, 3=事实核查",
        examples=[2]
    )
    
    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证内容不能为空白字符"""
        if not v.strip():
            raise ValueError("内容不能为空白字符")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "# 微服务架构演进\n\n微服务架构是一种...",
                "mode": 2
            }
        }


class ResumeRequest(BaseModel):
    """
    任务恢复请求模型
    
    用于 POST /api/v1/tasks/{task_id}/resume 接口
    用于在 interrupt 断点处注入人工修改的数据并恢复图执行
    """
    action: str = Field(
        ...,
        description="恢复动作类型",
        examples=["confirm_outline", "update_outline"]
    )
    
    data: Optional[dict[str, Any]] = Field(
        default=None,
        description="注入的数据（如修改后的大纲）",
        examples=[{"outline": [{"title": "第一章", "summary": "概述"}]}]
    )
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """验证动作类型"""
        allowed_actions = [
            "confirm_outline",
            "update_outline",
            "approve_draft",
            "reject_draft"
        ]
        if v not in allowed_actions:
            raise ValueError(f"不支持的动作类型: {v}，允许的值: {allowed_actions}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "action": "update_outline",
                "data": {
                    "outline": [
                        {
                            "title": "第一章：微服务概述",
                            "summary": "介绍微服务的基本概念"
                        },
                        {
                            "title": "第二章：架构演进",
                            "summary": "从单体到微服务的演进路径"
                        }
                    ]
                }
            }
        }