"""SQLite 任务持久化存储

使用 aiosqlite 将终态任务（completed / failed）和中断任务（interrupted）持久化到 SQLite。
运行中任务（running）继续用 _tasks dict 内存管理。

数据库路径：data/sqlite/craftflow.db（相对于 craftflow-backend/）
"""

from pathlib import Path
from typing import Any, Optional

import aiosqlite

from app.core.logger import get_logger

logger = get_logger(__name__)

# 数据库文件路径：craftflow-backend/data/sqlite/craftflow.db
_DB_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sqlite"
_DB_PATH = _DB_DIR / "craftflow.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    graph_type TEXT NOT NULL,
    status TEXT NOT NULL,
    topic TEXT,
    description TEXT,
    mode INTEGER,
    result TEXT,
    error TEXT,
    progress REAL DEFAULT 100.0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);
"""


class TaskStore:
    """SQLite 任务持久化存储（终态任务）

    任务完成后调用 save_task() 将结果写入 SQLite。
    历史页面通过 get_task_list() 一次查询获取全部任务。
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _DB_PATH
        self._db: Optional[aiosqlite.Connection] = None

    async def init_db(self) -> None:
        """初始化数据库连接和表结构"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute(_CREATE_TABLE_SQL)
        await self._db.execute(_CREATE_INDEX_SQL)
        await self._db.commit()
        logger.info(f"SQLite TaskStore 初始化完成 - {self._db_path}")

    async def save_task(self, task: dict[str, Any]) -> None:
        """保存或更新任务记录（INSERT OR REPLACE）

        Args:
            task: 任务数据字典，必须包含 task_id, graph_type, status, created_at, updated_at
        """
        if self._db is None:
            raise RuntimeError("TaskStore 未初始化，请先调用 init_db()")

        await self._db.execute(
            """INSERT OR REPLACE INTO tasks
            (task_id, graph_type, status, topic, description, mode,
             result, error, progress, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task["task_id"],
                task["graph_type"],
                task["status"],
                task.get("topic"),
                task.get("description"),
                task.get("mode"),
                task.get("result"),
                task.get("error"),
                task.get("progress", 100.0),
                task["created_at"],
                task["updated_at"],
            ),
        )
        await self._db.commit()
        logger.debug(f"任务已保存到 SQLite - task_id: {task['task_id']}")

    async def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        """根据 task_id 查询单个任务

        Returns:
            任务数据字典，不存在时返回 None
        """
        if self._db is None:
            raise RuntimeError("TaskStore 未初始化")

        cursor = await self._db.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_dict(cursor, row)

    async def get_interrupted_tasks(self) -> list[dict[str, Any]]:
        """查询所有中断状态的任务（用于服务重启后恢复到内存）

        Returns:
            中断状态的任务数据字典列表，按创建时间降序
        """
        if self._db is None:
            raise RuntimeError("TaskStore 未初始化")

        cursor = await self._db.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
            ("interrupted",),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]

    async def get_task_list(
        self, limit: int = 50, offset: int = 0,
    ) -> list[dict[str, Any]]:
        """查询任务列表（按创建时间降序）

        Args:
            limit: 最大返回数量
            offset: 偏移量（分页用）

        Returns:
            任务数据字典列表
        """
        if self._db is None:
            raise RuntimeError("TaskStore 未初始化")

        cursor = await self._db.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(cursor, row) for row in rows]

    async def delete_task(self, task_id: str) -> bool:
        """删除任务记录

        Returns:
            是否成功删除（True=有记录被删除，False=记录不存在）
        """
        if self._db is None:
            raise RuntimeError("TaskStore 未初始化")

        cursor = await self._db.execute(
            "DELETE FROM tasks WHERE task_id = ?", (task_id,),
        )
        await self._db.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug(f"任务已从 SQLite 删除 - task_id: {task_id}")
        return deleted

    async def close(self) -> None:
        """关闭数据库连接"""
        if self._db is not None:
            await self._db.close()
            self._db = None
            logger.info("SQLite TaskStore 连接已关闭")


def _row_to_dict(cursor: aiosqlite.Cursor, row: aiosqlite.Row) -> dict[str, Any]:
    """将数据库行转换为字典"""
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))
