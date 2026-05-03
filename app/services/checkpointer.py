"""Checkpointer 单例管理模块

根据环境变量选择 Checkpointer 实现：
- 开发环境：MemorySaver（内存存储，进程退出即丢失）
- 生产环境：PostgresSaver（PostgreSQL 持久化存储）

使用模块级单例确保全局只有一个 Checkpointer 实例。
"""

from typing import Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.core.exceptions import CheckpointerError
from app.core.logger import get_logger

logger = get_logger(__name__)

# 模块级单例
_checkpointer: Optional[BaseCheckpointSaver] = None


async def init_checkpointer() -> BaseCheckpointSaver:
    """初始化 Checkpointer 单例

    根据 settings.use_persistent_checkpointer 选择实现：
    - False → MemorySaver（开发环境）
    - True → PostgresSaver（生产环境，需要 PostgreSQL 连接）

    Returns:
        BaseCheckpointSaver: 初始化后的 Checkpointer 实例

    Raises:
        CheckpointerError: 初始化失败时抛出
    """
    global _checkpointer

    if _checkpointer is not None:
        logger.info("Checkpointer 已初始化，返回现有实例")
        return _checkpointer

    try:
        if settings.use_persistent_checkpointer:
            _checkpointer = await _create_postgres_saver()
            logger.info("PostgresSaver 初始化完成")
        else:
            _checkpointer = MemorySaver()
            logger.info("MemorySaver 初始化完成（开发模式，数据仅存于内存）")

        return _checkpointer

    except Exception as e:
        raise CheckpointerError(
            message=f"Checkpointer 初始化失败: {str(e)}",
            details={"use_persistent": settings.use_persistent_checkpointer},
        ) from e


def get_checkpointer() -> BaseCheckpointSaver:
    """获取已初始化的 Checkpointer 单例

    Returns:
        BaseCheckpointSaver: Checkpointer 实例

    Raises:
        CheckpointerError: Checkpointer 尚未初始化时抛出
    """
    if _checkpointer is None:
        raise CheckpointerError(
            message="Checkpointer 尚未初始化，请先调用 init_checkpointer()",
        )
    return _checkpointer


async def close_checkpointer() -> None:
    """关闭 Checkpointer，释放资源

    对于 PostgresSaver，关闭数据库连接池。
    对于 MemorySaver，清除引用等待 GC。
    """
    global _checkpointer

    if _checkpointer is None:
        return

    try:
        # PostgresSaver 可能有 conn 属性需要关闭
        if hasattr(_checkpointer, "conn") and _checkpointer.conn is not None:
            await _checkpointer.conn.close()
            logger.info("PostgresSaver 连接已关闭")
    except Exception as e:
        logger.warning(f"关闭 Checkpointer 时出错: {str(e)}")
    finally:
        _checkpointer = None
        logger.info("Checkpointer 已重置")


async def _create_postgres_saver() -> BaseCheckpointSaver:
    """创建 PostgresSaver 实例

    使用 AsyncPostgresSaver 连接 PostgreSQL 数据库。

    Returns:
        BaseCheckpointSaver: PostgresSaver 实例

    Raises:
        CheckpointerError: 连接失败时抛出
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        saver = AsyncPostgresSaver.from_conn_string(settings.database_url)
        await saver.setup()
        return saver

    except ImportError as e:
        raise CheckpointerError(
            message="PostgresSaver 依赖未安装，请安装 langgraph-checkpoint-postgres",
            details={"missing_package": "langgraph-checkpoint-postgres"},
        ) from e
    except Exception as e:
        raise CheckpointerError(
            message=f"PostgreSQL 连接失败: {str(e)}",
            details={"database_url": settings.database_url},
        ) from e


def reset_checkpointer() -> None:
    """重置 Checkpointer 单例（仅用于测试）

    警告：此方法仅应在测试中调用，生产环境使用 close_checkpointer()。
    """
    global _checkpointer
    _checkpointer = None
