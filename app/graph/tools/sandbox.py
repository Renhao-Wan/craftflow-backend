"""代码沙箱工具封装

封装 E2B Code Interpreter，提供安全的代码执行环境。
支持 Python 代码执行、文件操作和结果验证。
"""

import asyncio
from typing import Any

from langchain_core.tools import tool

from app.core.config import settings
from app.core.exceptions import ToolExecutionError
from app.core.logger import logger

# E2B 导入（延迟导入以避免未安装时报错）
try:
    from e2b_code_interpreter import Sandbox as E2BSandbox
except ImportError:
    E2BSandbox = None
    logger.warning("e2b_code_interpreter 未安装，代码沙箱功能将不可用")


class E2BSandboxManager:
    """E2B 代码沙箱管理器

    提供沙箱生命周期管理、代码执行和结果处理。
    """

    @staticmethod
    def _check_availability() -> None:
        """检查 E2B 是否可用

        Raises:
            ToolExecutionError: 当 E2B 不可用时抛出
        """
        if E2BSandbox is None:
            raise ToolExecutionError(
                tool_name="E2BSandbox",
                message="e2b_code_interpreter 未安装，请运行: pip install e2b-code-interpreter",
            )

        if not settings.e2b_api_key:
            raise ToolExecutionError(
                tool_name="E2BSandbox",
                message="E2B_API_KEY 未配置，请在 .env 文件中设置",
            )

    @staticmethod
    async def execute_code(
        code: str, timeout: int = 30, language: str = "python"
    ) -> dict[str, Any]:
        """在沙箱中执行代码

        Args:
            code: 要执行的代码字符串
            timeout: 执行超时时间（秒），默认 30 秒
            language: 编程语言，目前仅支持 "python"

        Returns:
            dict: 执行结果，包含：
                - success: 是否成功执行
                - output: 标准输出
                - error: 错误信息（如果有）
                - execution_time: 执行时间（秒）

        Raises:
            ToolExecutionError: 执行失败时抛出
        """
        E2BSandboxManager._check_availability()

        if language != "python":
            raise ToolExecutionError(
                tool_name="E2BSandbox",
                message=f"不支持的语言: {language}，目前仅支持 Python",
            )

        sandbox = None
        try:
            logger.info(f"创建 E2B 沙箱，准备执行代码（超时: {timeout}s）")

            # 使用 Sandbox.create() 创建沙箱实例（新版 API）
            # 注意：新版 E2B SDK 使用 Sandbox.create() 而不是直接初始化
            sandbox = E2BSandbox.create(api_key=settings.e2b_api_key)

            # 执行代码
            execution = sandbox.run_code(code, timeout=timeout)

            # 处理结果
            result = {
                "success": not execution.error,
                "output": "",
                "error": None,
                "execution_time": 0.0,
            }

            # 收集输出
            if execution.logs:
                if execution.logs.stdout:
                    result["output"] = "\n".join(execution.logs.stdout)
                if execution.logs.stderr:
                    stderr_output = "\n".join(execution.logs.stderr)
                    if stderr_output:
                        result["error"] = stderr_output

            # 收集错误
            if execution.error:
                result["error"] = str(execution.error)
                logger.warning(f"代码执行出错: {execution.error}")
            else:
                logger.info("代码执行成功")

            return result

        except asyncio.TimeoutError:
            error_msg = f"代码执行超时（{timeout}s）"
            logger.error(error_msg)
            raise ToolExecutionError(tool_name="E2BSandbox", message=error_msg)

        except Exception as e:
            error_msg = f"沙箱执行失败: {str(e)}"
            logger.error(error_msg)
            raise ToolExecutionError(tool_name="E2BSandbox", message=error_msg) from e

        finally:
            # 确保沙箱被关闭
            if sandbox:
                try:
                    sandbox.kill()
                    logger.debug("E2B 沙箱已关闭")
                except Exception as e:
                    logger.warning(f"关闭沙箱时出错: {e}")


@tool
def execute_python_code(code: str, timeout: int = 30) -> dict[str, Any]:
    """在安全沙箱中执行 Python 代码

    使用 E2B Code Interpreter 提供隔离的执行环境，
    适用于验证代码示例、计算结果等场景。

    Args:
        code: 要执行的 Python 代码字符串
        timeout: 执行超时时间（秒），默认 30 秒

    Returns:
        dict: 执行结果，包含：
            - success: 是否成功执行
            - output: 标准输出
            - error: 错误信息（如果有）

    Examples:
        >>> result = execute_python_code("print('Hello, World!')")
        >>> print(result["output"])
        "Hello, World!"
        
    Note:
        如果 E2B 不可用或执行失败，将返回降级响应，不会抛出异常。
    """
    logger.info("开始执行 Python 代码")

    try:
        # 使用 asyncio.run 在同步上下文中调用异步方法
        result = asyncio.run(E2BSandboxManager.execute_code(code, timeout, "python"))
        return result

    except ToolExecutionError as e:
        # E2B 不可用或配置错误，返回降级响应
        logger.warning(f"E2B 沙箱不可用，返回降级响应: {e.message}")
        return {
            "success": False,
            "output": "",
            "error": f"代码沙箱不可用: {e.message}",
        }

    except Exception as e:
        # 其他未预期的错误，返回降级响应
        logger.error(f"代码执行出现未预期错误: {str(e)}")
        return {
            "success": False,
            "output": "",
            "error": f"代码执行失败: {str(e)}",
        }


@tool
def validate_code_snippet(code: str, expected_output: str | None = None) -> dict[str, Any]:
    """验证代码片段的正确性

    执行代码并可选地验证输出是否符合预期。
    适用于文章中代码示例的自动化验证。

    Args:
        code: 要验证的 Python 代码字符串
        expected_output: 期望的输出（可选），如果提供则进行匹配验证

    Returns:
        dict: 验证结果，包含：
            - valid: 代码是否有效
            - output: 实际输出
            - matches_expected: 是否匹配期望输出（如果提供了 expected_output）
            - error: 错误信息（如果有）

    Examples:
        >>> result = validate_code_snippet(
        ...     code="print(2 + 2)",
        ...     expected_output="4"
        ... )
        >>> print(result["valid"])
        True
        
    Note:
        如果 E2B 不可用或执行失败，将返回降级响应，不会抛出异常。
    """
    logger.info("开始验证代码片段")

    try:
        # 执行代码
        exec_result = asyncio.run(E2BSandboxManager.execute_code(code, timeout=15, language="python"))

        # 构建验证结果
        result = {
            "valid": exec_result["success"],
            "output": exec_result["output"],
            "error": exec_result["error"],
            "matches_expected": None,
        }

        # 如果提供了期望输出，进行匹配验证
        if expected_output is not None:
            actual_output = exec_result["output"].strip()
            expected_output_clean = expected_output.strip()
            result["matches_expected"] = actual_output == expected_output_clean

            if result["matches_expected"]:
                logger.info("代码输出匹配期望值")
            else:
                logger.warning(
                    f"代码输出不匹配 - 期望: '{expected_output_clean}', 实际: '{actual_output}'"
                )

        return result

    except ToolExecutionError as e:
        # E2B 不可用或配置错误，返回降级响应
        logger.warning(f"E2B 沙箱不可用，返回降级响应: {e.message}")
        return {
            "valid": False,
            "output": "",
            "error": f"代码沙箱不可用: {e.message}",
            "matches_expected": None,
        }

    except Exception as e:
        # 其他未预期的错误，返回降级响应
        logger.error(f"代码验证出现未预期错误: {str(e)}")
        return {
            "valid": False,
            "output": "",
            "error": f"代码验证失败: {str(e)}",
            "matches_expected": None,
        }


# 导出工具列表（供 LangGraph 节点绑定）
SANDBOX_TOOLS = [execute_python_code, validate_code_snippet]
