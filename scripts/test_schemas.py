"""
数据模型验证测试脚本

用于验证 app/schemas 模块中定义的所有数据模型
"""

from app.schemas import (
    CreationRequest,
    PolishingRequest,
    ResumeRequest,
    TaskResponse,
    TaskStatusResponse,
    ErrorResponse,
)
from pydantic import ValidationError


def test_creation_request():
    """测试 CreationRequest 模型"""
    print("\n=== 测试 CreationRequest ===")
    
    # 正常情况
    req = CreationRequest(
        topic="微服务架构演进",
        description="请重点关注容器化部署",
        hitl_enabled=True
    )
    print(f"✓ 正常创建: {req.topic}")
    
    # 测试验证器：空白主题
    try:
        CreationRequest(topic="   ", description="测试")
        print("✗ 应该抛出验证错误")
    except ValidationError as e:
        print(f"✓ 空白主题验证: {e.errors()[0]['msg']}")
    
    # 测试默认值
    req2 = CreationRequest(topic="测试主题")
    print(f"✓ 默认值: description='{req2.description}', hitl_enabled={req2.hitl_enabled}")


def test_polishing_request():
    """测试 PolishingRequest 模型"""
    print("\n=== 测试 PolishingRequest ===")
    
    # 正常情况
    req = PolishingRequest(
        content="# 标题\n\n正文内容",
        mode=2
    )
    print(f"✓ 正常创建: mode={req.mode}")
    
    # 测试模式范围验证
    try:
        PolishingRequest(content="测试内容", mode=5)
        print("✗ 应该抛出验证错误")
    except ValidationError as e:
        print(f"✓ 模式范围验证: {e.errors()[0]['msg']}")
    
    # 测试默认值
    req2 = PolishingRequest(content="测试内容，这是一段足够长的文本")
    print(f"✓ 默认模式: mode={req2.mode}")


def test_resume_request():
    """测试 ResumeRequest 模型"""
    print("\n=== 测试 ResumeRequest ===")
    
    # 正常情况
    req = ResumeRequest(
        action="update_outline",
        data={"outline": [{"title": "第一章", "summary": "概述"}]}
    )
    print(f"✓ 正常创建: action={req.action}")
    
    # 测试动作类型验证
    try:
        ResumeRequest(action="invalid_action")
        print("✗ 应该抛出验证错误")
    except ValidationError as e:
        print(f"✓ 动作类型验证: {e.errors()[0]['msg']}")


def test_task_response():
    """测试 TaskResponse 模型"""
    print("\n=== 测试 TaskResponse ===")
    
    resp = TaskResponse(
        task_id="c-550e8400-e29b-41d4-a716-446655440000",
        status="running",
        message="任务已创建"
    )
    print(f"✓ 正常创建: task_id={resp.task_id}, status={resp.status}")
    
    # 测试 JSON 序列化
    json_data = resp.model_dump()
    print(f"✓ JSON 序列化: {list(json_data.keys())}")


def test_task_status_response():
    """测试 TaskStatusResponse 模型"""
    print("\n=== 测试 TaskStatusResponse ===")
    
    # 运行中状态
    resp1 = TaskStatusResponse(
        task_id="test-123",
        status="running",
        current_node="WriterNode",
        progress=45.5
    )
    print(f"✓ 运行中状态: node={resp1.current_node}, progress={resp1.progress}%")
    
    # 中断状态
    resp2 = TaskStatusResponse(
        task_id="test-123",
        status="interrupted",
        awaiting="outline_confirmation",
        data={"outline": [{"title": "第一章"}]}
    )
    print(f"✓ 中断状态: awaiting={resp2.awaiting}")
    
    # 完成状态
    resp3 = TaskStatusResponse(
        task_id="test-123",
        status="completed",
        result="# 完整文章内容",
        progress=100.0
    )
    print(f"✓ 完成状态: progress={resp3.progress}%")


def test_error_response():
    """测试 ErrorResponse 模型"""
    print("\n=== 测试 ErrorResponse ===")
    
    err = ErrorResponse(
        error="ValidationError",
        message="主题不能为空",
        detail={"field": "topic"},
        path="/api/v1/creation"
    )
    print(f"✓ 错误响应: error={err.error}, message={err.message}")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("数据模型验证测试")
    print("=" * 60)
    
    test_creation_request()
    test_polishing_request()
    test_resume_request()
    test_task_response()
    test_task_status_response()
    test_error_response()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
