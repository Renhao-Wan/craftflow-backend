"""Checkpointer 单例管理模块

根据 settings.checkpointer_backend 选择 Checkpointer 实现：
- memory   → MemorySaver（内存存储，进程退出即丢失，适合快速调试）
- sqlite   → SqliteSaver（SQLite 持久化，零配置，开发/小规模部署推荐）
- postgres → PostgresSaver（PostgreSQL 持久化，生产环境推荐）

数据库文件统一存放在 data/ 目录下：
- data/checkpoints/checkpoints.db  （SqliteSaver）
- data/sqlite/craftflow.db          （TaskStore）
- data/chroma_db/                  （Chroma 向量数据库）

使用模块级单例确保全局只有一个 Checkpointer 实例。
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import aiosqlite
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from app.core.config import settings
from app.core.exceptions import CheckpointerError
from app.core.logger import get_logger

logger = get_logger(__name__)

# 数据目录根路径：craftflow-backend/data/
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# 模块级单例
_checkpointer: Optional[BaseCheckpointSaver] = None
_closer: Optional["_Closer"] = None


# ============================================
# 抽象工厂
# ============================================


class _Closer(ABC):
    """Checkpointer 资源释放接口"""

    @abstractmethod
    async def close(self) -> None:
        ...


class CheckpointerFactory(ABC):
    """Checkpointer 创建工厂基类"""

    @abstractmethod
    async def create(self) -> tuple[BaseCheckpointSaver, _Closer]:
        """创建 Checkpointer 实例和对应的 Closer

        Returns:
            (checkpointer, closer) 元组
        """
        ...


# ============================================
# 具体工厂实现
# ============================================


class MemoryCheckpointerFactory(CheckpointerFactory):
    """MemorySaver 工厂（内存存储，无需清理）"""

    async def create(self) -> tuple[BaseCheckpointSaver, _Closer]:
        saver = MemorySaver()

        class _NoopCloser(_Closer):
            async def close(self) -> None:
                pass

        return saver, _NoopCloser()


class SqliteCheckpointerFactory(CheckpointerFactory):
    """SqliteSaver 工厂（SQLite 持久化）

    数据库路径：data/checkpoints/checkpoints.db
    """

    DB_PATH = DATA_DIR / "checkpoints" / "checkpoints.db"

    async def create(self) -> tuple[BaseCheckpointSaver, _Closer]:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(self.DB_PATH))
        saver = AsyncSqliteSaver(conn)
        await saver.setup()

        class _SqliteCloser(_Closer):
            def __init__(self, c: aiosqlite.Connection):
                self._conn = c

            async def close(self) -> None:
                await self._conn.close()

        return saver, _SqliteCloser(conn)


class PostgresCheckpointerFactory(CheckpointerFactory):
    """PostgresSaver 工厂（PostgreSQL 持久化）"""

    async def create(self) -> tuple[BaseCheckpointSaver, _Closer]:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        except ImportError as e:
            raise CheckpointerError(
                message="PostgresSaver 依赖未安装，请安装 langgraph-checkpoint-postgres",
                details={"missing_package": "langgraph-checkpoint-postgres"},
            ) from e

        try:
            saver = AsyncPostgresSaver.from_conn_string(settings.database_url)
            await saver.setup()
        except Exception as e:
            raise CheckpointerError(
                message=f"PostgreSQL 连接失败: {str(e)}",
                details={"database_url": settings.database_url},
            ) from e

        class _PostgresCloser(_Closer):
            def __init__(self, s: BaseCheckpointSaver):
                self._saver = s

            async def close(self) -> None:
                if hasattr(self._saver, "conn") and self._saver.conn is not None:
                    await self._saver.conn.close()

        return saver, _PostgresCloser(saver)


# 后端 → 工厂映射
_FACTORIES: dict[str, CheckpointerFactory] = {
    "memory": MemoryCheckpointerFactory(),
    "sqlite": SqliteCheckpointerFactory(),
    "postgres": PostgresCheckpointerFactory(),
}


# ============================================
# 模块级 API
# ============================================


async def init_checkpointer() -> BaseCheckpointSaver:
    """初始化 Checkpointer 单例

    根据 settings.checkpointer_backend 选择对应工厂创建实例。

    Returns:
        BaseCheckpointSaver: 初始化后的 Checkpointer 实例

    Raises:
        CheckpointerError: 初始化失败或后端名称无效时抛出
    """
    global _checkpointer, _closer

    if _checkpointer is not None:
        logger.info("Checkpointer 已初始化，返回现有实例")
        return _checkpointer

    backend = settings.checkpointer_backend
    factory = _FACTORIES.get(backend)
    if factory is None:
        raise CheckpointerError(
            message=f"未知的 Checkpointer 后端: {backend}",
            details={"valid_backends": list(_FACTORIES.keys())},
        )

    try:
        _checkpointer, _closer = await factory.create()
        logger.info(f"Checkpointer 初始化完成 - 后端: {backend}")
        return _checkpointer
    except CheckpointerError:
        raise
    except Exception as e:
        raise CheckpointerError(
            message=f"Checkpointer 初始化失败: {str(e)}",
            details={"backend": backend},
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
    """关闭 Checkpointer，释放资源"""
    global _checkpointer, _closer

    if _checkpointer is None:
        return

    try:
        if _closer is not None:
            await _closer.close()
    except Exception as e:
        logger.warning(f"关闭 Checkpointer 时出错: {str(e)}")
    finally:
        _checkpointer = None
        _closer = None
        logger.info("Checkpointer 已重置")


async def cleanup_checkpoint(thread_id: str) -> None:
    """清理指定 thread_id 的 checkpoint 数据（通用接口）

    任务完成/失败后调用，释放 checkpoint 存储空间。
    不依赖具体的 Checkpointer 实现，通过 BaseCheckpointSaver 的通用方法操作。

    Args:
        thread_id: 要清理的 thread_id（等于 task_id）
    """
    if _checkpointer is None:
        return

    try:
        await _checkpointer.adelete_thread(thread_id)
        logger.debug(f"Checkpoint 已清理 - thread_id: {thread_id}")
    except Exception as e:
        logger.warning(f"清理 checkpoint 失败 - thread_id: {thread_id}, error: {e}")


def reset_checkpointer() -> None:
    """重置 Checkpointer 单例（仅用于测试）

    警告：此方法仅应在测试中调用，生产环境使用 close_checkpointer()。
    """
    global _checkpointer, _closer
    _checkpointer = None
    _closer = None
