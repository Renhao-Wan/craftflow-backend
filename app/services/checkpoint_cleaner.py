"""MemorySaver checkpoint 清理模块

任务完成后从 MemorySaver 中清除对应 thread_id 的 checkpoint 数据，释放内存。

MemorySaver 内部存储结构：
- storage[thread_id][checkpoint_ns][checkpoint_id] = (checkpoint, metadata, parent)
- writes[thread_id][...] = ...
- blobs[(thread_id, ns, key, version)] = blob_data
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from app.core.logger import get_logger

logger = get_logger(__name__)


async def cleanup_checkpoint(
    checkpointer: BaseCheckpointSaver,
    thread_id: str,
) -> None:
    """从 MemorySaver 清除指定 thread_id 的所有 checkpoint 数据

    仅对 MemorySaver 实例生效，PostgresSaver 等其他实现会跳过。

    Args:
        checkpointer: LangGraph Checkpointer 实例
        thread_id: 要清理的 thread_id（等于 task_id）
    """
    if not isinstance(checkpointer, MemorySaver):
        logger.debug(f"跳过 checkpoint 清理（非 MemorySaver）- thread_id: {thread_id}")
        return

    try:
        # 1. 清除 storage 中的 checkpoint
        if thread_id in checkpointer.storage:
            del checkpointer.storage[thread_id]

        # 2. 清除 writes 中的数据
        if thread_id in checkpointer.writes:
            del checkpointer.writes[thread_id]

        # 3. 清除 blobs 中以 thread_id 开头的条目
        keys_to_delete = [
            k for k in checkpointer.blobs if k[0] == thread_id
        ]
        for k in keys_to_delete:
            del checkpointer.blobs[k]

        logger.info(
            f"MemorySaver checkpoint 已清理 - thread_id: {thread_id}"
        )

    except Exception as e:
        logger.warning(f"清理 checkpoint 失败 - thread_id: {thread_id}, error: {e}")
