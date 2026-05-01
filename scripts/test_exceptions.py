"""异常处理验证脚本

用于测试自定义异常类是否正常工作。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core import (
    CheckpointerError,
    GraphExecutionError,
    LLMProviderError,
    TaskNotFoundError,
    TaskTimeoutError,
    ToolExecutionError,
    ValidationError,
    logger,
    setup_logger,
)


def test_exceptions():
    """测试各种自定义异常"""
    setup_logger()
    
    logger.info("=" * 60)
    logger.info("CraftFlow 异常处理验证")
    logger.info("=" * 60)
    
    # 测试 TaskNotFoundError
    try:
        raise TaskNotFoundError(task_id="test-task-123")
    except TaskNotFoundError as e:
        logger.info(f"\n✓ TaskNotFoundError 测试通过")
        logger.info(f"  错误码: {e.error_code}")
        logger.info(f"  消息: {e.message}")
        logger.info(f"  状态码: {e.status_code}")
        logger.info(f"  详情: {e.details}")
    
    # 测试 GraphExecutionError
    try:
        raise GraphExecutionError(
            message="节点执行失败",
            details={"node": "PlannerNode", "reason": "LLM 超时"}
        )
    except GraphExecutionError as e:
        logger.info(f"\n✓ GraphExecutionError 测试通过")
        logger.info(f"  错误码: {e.error_code}")
        logger.info(f"  消息: {e.message}")
        logger.info(f"  详情: {e.details}")
    
    # 测试 LLMProviderError
    try:
        raise LLMProviderError(
            message="API 限流",
            provider="OpenAI",
            details={"retry_after": 60}
        )
    except LLMProviderError as e:
        logger.info(f"\n✓ LLMProviderError 测试通过")
        logger.info(f"  错误码: {e.error_code}")
        logger.info(f"  消息: {e.message}")
        logger.info(f"  详情: {e.details}")
    
    # 测试 ToolExecutionError
    try:
        raise ToolExecutionError(
            tool_name="TavilySearch",
            message="搜索 API 返回 500",
            details={"query": "test query"}
        )
    except ToolExecutionError as e:
        logger.info(f"\n✓ ToolExecutionError 测试通过")
        logger.info(f"  错误码: {e.error_code}")
        logger.info(f"  消息: {e.message}")
        logger.info(f"  详情: {e.details}")
    
    # 测试 ValidationError
    try:
        raise ValidationError(
            message="主题不能为空",
            field="topic"
        )
    except ValidationError as e:
        logger.info(f"\n✓ ValidationError 测试通过")
        logger.info(f"  错误码: {e.error_code}")
        logger.info(f"  消息: {e.message}")
        logger.info(f"  状态码: {e.status_code}")
        logger.info(f"  详情: {e.details}")
    
    # 测试 TaskTimeoutError
    try:
        raise TaskTimeoutError(task_id="test-task-456", timeout=3600)
    except TaskTimeoutError as e:
        logger.info(f"\n✓ TaskTimeoutError 测试通过")
        logger.info(f"  错误码: {e.error_code}")
        logger.info(f"  消息: {e.message}")
        logger.info(f"  详情: {e.details}")
    
    # 测试 CheckpointerError
    try:
        raise CheckpointerError(
            message="数据库连接失败",
            details={"db_url": "postgresql://..."}
        )
    except CheckpointerError as e:
        logger.info(f"\n✓ CheckpointerError 测试通过")
        logger.info(f"  错误码: {e.error_code}")
        logger.info(f"  消息: {e.message}")
        logger.info(f"  详情: {e.details}")
    
    logger.info("\n" + "=" * 60)
    logger.success("✓ 所有异常测试通过")
    logger.info("=" * 60)


if __name__ == "__main__":
    test_exceptions()
