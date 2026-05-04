"""自定义异常类与全局异常处理器

定义业务异常类型，并提供 FastAPI 全局异常处理器。
"""

from typing import Any
from datetime import datetime

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logger import logger

# ============================================
# 自定义异常类
# ============================================


class CraftFlowException(Exception):
    """CraftFlow 基础异常类

    所有业务异常的基类，包含错误码和详细信息。
    """

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ):
        """初始化异常

        Args:
            message: 错误消息
            error_code: 错误码（用于前端识别）
            status_code: HTTP 状态码
            details: 额外的错误详情
        """
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class GraphExecutionError(CraftFlowException):
    """Graph 执行异常

    当 LangGraph 执行过程中发生错误时抛出。
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="GRAPH_EXECUTION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class CheckpointerError(CraftFlowException):
    """Checkpointer 异常

    当状态持久化操作失败时抛出。
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=message,
            error_code="CHECKPOINTER_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class TaskNotFoundError(CraftFlowException):
    """任务不存在异常

    当查询的任务 ID 不存在时抛出。
    """

    def __init__(self, task_id: str):
        super().__init__(
            message=f"任务不存在: {task_id}",
            error_code="TASK_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"task_id": task_id},
        )


class TaskTimeoutError(CraftFlowException):
    """任务超时异常

    当任务执行超过配置的超时时间时抛出。
    """

    def __init__(self, task_id: str, timeout: int):
        super().__init__(
            message=f"任务执行超时: {task_id} (超时时间: {timeout}秒)",
            error_code="TASK_TIMEOUT",
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            details={"task_id": task_id, "timeout": timeout},
        )


class LLMProviderError(CraftFlowException):
    """LLM 提供商异常

    当 LLM API 调用失败时抛出。
    """

    def __init__(self, message: str, provider: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=f"LLM 提供商错误 ({provider}): {message}",
            error_code="LLM_PROVIDER_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"provider": provider, **(details or {})},
        )


class ToolExecutionError(CraftFlowException):
    """工具执行异常

    当外部工具（搜索、沙箱等）调用失败时抛出。
    """

    def __init__(self, tool_name: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            message=f"工具执行失败 ({tool_name}): {message}",
            error_code="TOOL_EXECUTION_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"tool_name": tool_name, **(details or {})},
        )


class ValidationError(CraftFlowException):
    """业务验证异常

    当业务逻辑验证失败时抛出（区别于 Pydantic 的请求验证）。
    """

    def __init__(self, message: str, field: str | None = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"field": field} if field else {},
        )


# ============================================
# 全局异常处理器
# ============================================


async def craftflow_exception_handler(request: Request, exc: CraftFlowException) -> JSONResponse:
    """处理 CraftFlow 自定义异常

    Args:
        request: FastAPI 请求对象
        exc: CraftFlow 异常实例

    Returns:
        JSON 格式的错误响应
    """
    from app.schemas.response import ErrorResponse
    
    logger.error(
        f"业务异常 | 路径: {request.url.path} | "
        f"错误码: {exc.error_code} | 消息: {exc.message} | "
        f"详情: {exc.details}"
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.error_code,
            message=exc.message,
            detail=exc.details,
            timestamp=datetime.now(),
            path=str(request.url.path),
        ).model_dump(mode='json'),
    )


def _clean_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """清理验证错误中的不可序列化对象

    Pydantic 验证错误的 ctx 字段可能包含 Exception 对象，
    无法直接 JSON 序列化。此函数将其转换为字符串。

    Args:
        errors: Pydantic 原始错误列表

    Returns:
        清理后的错误列表
    """
    cleaned = []
    for error in errors:
        clean_error = {}
        for key, value in error.items():
            if key == "ctx" and isinstance(value, dict):
                clean_error[key] = {
                    k: str(v) if isinstance(v, Exception) else v
                    for k, v in value.items()
                }
            elif isinstance(value, Exception):
                clean_error[key] = str(value)
            else:
                clean_error[key] = value
        cleaned.append(clean_error)
    return cleaned


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理 Pydantic 请求验证异常

    Args:
        request: FastAPI 请求对象
        exc: Pydantic 验证异常

    Returns:
        JSON 格式的错误响应
    """
    from app.schemas.response import ErrorResponse

    errors = _clean_validation_errors(exc.errors())
    logger.warning(f"请求验证失败 | 路径: {request.url.path} | 错误: {errors}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="REQUEST_VALIDATION_ERROR",
            message="请求参数验证失败",
            detail={"errors": errors},
            timestamp=datetime.now(),
            path=str(request.url.path),
        ).model_dump(mode='json'),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理未捕获的通用异常

    Args:
        request: FastAPI 请求对象
        exc: 通用异常

    Returns:
        JSON 格式的错误响应
    """
    from app.schemas.response import ErrorResponse
    
    logger.exception(
        f"未捕获异常 | 路径: {request.url.path} | 类型: {type(exc).__name__} | " f"消息: {str(exc)}"
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="INTERNAL_SERVER_ERROR",
            message="服务器内部错误，请稍后重试",
            detail={"exception_type": type(exc).__name__},
            timestamp=datetime.now(),
            path=str(request.url.path),
        ).model_dump(mode='json'),
    )


# ============================================
# 异常处理器注册函数
# ============================================


def register_exception_handlers(app) -> None:
    """注册所有异常处理器到 FastAPI 应用

    Args:
        app: FastAPI 应用实例
    """
    app.add_exception_handler(CraftFlowException, craftflow_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("全局异常处理器注册完成")
