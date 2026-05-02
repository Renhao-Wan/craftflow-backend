"""
异常处理测试脚本

验证自定义异常类和全局异常处理器的功能
"""

import asyncio
from unittest.mock import Mock

from fastapi import Request
from fastapi.exceptions import RequestValidationError

from app.core.exceptions import (
    CraftFlowException,
    TaskNotFoundError,
    GraphExecutionError,
    LLMProviderError,
    craftflow_exception_handler,
    validation_exception_handler,
    generic_exception_handler,
)
from app.schemas.response import ErrorResponse


async def test_craftflow_exception_handler():
    """测试 CraftFlow 自定义异常处理器"""
    print("\n=== 测试 CraftFlow 异常处理器 ===")
    
    # 创建模拟请求
    request = Mock(spec=Request)
    request.url.path = "/api/v1/tasks/test-123"
    
    # 创建异常
    exc = TaskNotFoundError(task_id="test-123")
    
    # 调用处理器
    response = await craftflow_exception_handler(request, exc)
    
    # 验证响应
    assert response.status_code == 404
    content = response.body.decode()
    print(f"✓ 状态码: {response.status_code}")
    print(f"✓ 响应内容: {content[:100]}...")
    
    # 验证响应格式符合 ErrorResponse
    import json
    data = json.loads(content)
    assert "error" in data
    assert "message" in data
    assert "timestamp" in data
    assert "path" in data
    print(f"✓ 响应格式符合 ErrorResponse 模型")


async def test_validation_exception_handler():
    """测试请求验证异常处理器"""
    print("\n=== 测试请求验证异常处理器 ===")
    
    # 创建模拟请求
    request = Mock(spec=Request)
    request.url.path = "/api/v1/creation"
    
    # 创建验证异常（模拟）
    from pydantic import ValidationError as PydanticValidationError
    
    try:
        from app.schemas import CreationRequest
        CreationRequest(topic="")  # 触发验证错误
    except PydanticValidationError as exc:
        # 转换为 RequestValidationError
        from fastapi.exceptions import RequestValidationError
        validation_exc = RequestValidationError(errors=exc.errors())
        
        # 调用处理器
        response = await validation_exception_handler(request, validation_exc)
        
        # 验证响应
        assert response.status_code == 422
        content = response.body.decode()
        print(f"✓ 状态码: {response.status_code}")
        print(f"✓ 响应内容: {content[:150]}...")
        
        # 验证响应格式
        import json
        data = json.loads(content)
        assert data["error"] == "REQUEST_VALIDATION_ERROR"
        assert "errors" in data["detail"]
        print(f"✓ 响应格式符合 ErrorResponse 模型")


async def test_generic_exception_handler():
    """测试通用异常处理器"""
    print("\n=== 测试通用异常处理器 ===")
    
    # 创建模拟请求
    request = Mock(spec=Request)
    request.url.path = "/api/v1/polishing"
    
    # 创建通用异常
    exc = ValueError("意外的错误")
    
    # 调用处理器
    response = await generic_exception_handler(request, exc)
    
    # 验证响应
    assert response.status_code == 500
    content = response.body.decode()
    print(f"✓ 状态码: {response.status_code}")
    print(f"✓ 响应内容: {content[:100]}...")
    
    # 验证响应格式
    import json
    data = json.loads(content)
    assert data["error"] == "INTERNAL_SERVER_ERROR"
    assert data["detail"]["exception_type"] == "ValueError"
    print(f"✓ 响应格式符合 ErrorResponse 模型")


def test_exception_classes():
    """测试自定义异常类"""
    print("\n=== 测试自定义异常类 ===")
    
    # TaskNotFoundError
    exc1 = TaskNotFoundError(task_id="abc-123")
    assert exc1.error_code == "TASK_NOT_FOUND"
    assert exc1.status_code == 404
    assert exc1.details["task_id"] == "abc-123"
    print(f"✓ TaskNotFoundError: {exc1.message}")
    
    # GraphExecutionError
    exc2 = GraphExecutionError(message="节点执行失败", details={"node": "WriterNode"})
    assert exc2.error_code == "GRAPH_EXECUTION_ERROR"
    assert exc2.status_code == 500
    print(f"✓ GraphExecutionError: {exc2.message}")
    
    # LLMProviderError
    exc3 = LLMProviderError(message="API 限流", provider="openai")
    assert exc3.error_code == "LLM_PROVIDER_ERROR"
    assert exc3.details["provider"] == "openai"
    print(f"✓ LLMProviderError: {exc3.message}")


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("异常处理测试")
    print("=" * 60)
    
    test_exception_classes()
    await test_craftflow_exception_handler()
    await test_validation_exception_handler()
    await test_generic_exception_handler()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
