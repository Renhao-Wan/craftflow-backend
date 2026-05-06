"""FastAPI 依赖注入模块

提供全局共享的服务实例，通过 FastAPI 的 Depends() 机制注入到路由中。

依赖链：
    checkpointer + task_store → CreationService / PolishingService
    （checkpointer 和 task_store 在应用启动时初始化）

使用方式：
    @router.post("/creation")
    async def create_task(
        request: CreationRequest,
        service: CreationService = Depends(get_creation_service),
    ):
        ...
"""

from app.core.exceptions import CheckpointerError
from app.core.logger import get_logger
from app.services.checkpointer import get_checkpointer
from app.services.creation_svc import CreationService
from app.services.polishing_svc import PolishingService
from app.services.task_store import TaskStore

logger = get_logger(__name__)

# ============================================
# 模块级单例（应用启动后初始化）
# ============================================

_creation_service: CreationService | None = None
_polishing_service: PolishingService | None = None
_task_store: TaskStore | None = None


async def init_services() -> None:
    """初始化所有业务服务

    在应用启动时调用，必须在 init_checkpointer() 之后执行。

    Raises:
        CheckpointerError: Checkpointer 尚未初始化
    """
    global _creation_service, _polishing_service, _task_store

    checkpointer = get_checkpointer()

    _task_store = TaskStore()
    await _task_store.init_db()

    _creation_service = CreationService(checkpointer=checkpointer, task_store=_task_store)
    _polishing_service = PolishingService(checkpointer=checkpointer, task_store=_task_store)

    logger.info("业务服务初始化完成（CreationService, PolishingService, TaskStore）")


async def close_services() -> None:
    """关闭所有业务服务，释放资源"""
    global _creation_service, _polishing_service, _task_store

    if _task_store:
        await _task_store.close()
    _creation_service = None
    _polishing_service = None
    _task_store = None

    logger.info("业务服务已关闭")


# ============================================
# FastAPI 依赖注入函数
# ============================================


def get_creation_service() -> CreationService:
    """获取 CreationService 实例（FastAPI 依赖注入）

    Returns:
        CreationService: 创作业务服务实例

    Raises:
        CheckpointerError: 服务尚未初始化时抛出
    """
    if _creation_service is None:
        raise CheckpointerError(
            message="CreationService 尚未初始化，请确保应用已启动",
        )
    return _creation_service


def get_polishing_service() -> PolishingService:
    """获取 PolishingService 实例（FastAPI 依赖注入）

    Returns:
        PolishingService: 润色业务服务实例

    Raises:
        CheckpointerError: 服务尚未初始化时抛出
    """
    if _polishing_service is None:
        raise CheckpointerError(
            message="PolishingService 尚未初始化，请确保应用已启动",
        )
    return _polishing_service


def get_task_store() -> TaskStore:
    """获取 TaskStore 实例（FastAPI 依赖注入）

    Returns:
        TaskStore: SQLite 任务持久化存储实例

    Raises:
        CheckpointerError: 服务尚未初始化时抛出
    """
    if _task_store is None:
        raise CheckpointerError(
            message="TaskStore 尚未初始化，请确保应用已启动",
        )
    return _task_store
