"""Creation 业务服务层

封装 Creation Graph 的业务逻辑，包括：
- 任务创建（发起创作流程）
- 任务状态查询
- 任务恢复（HITL 大纲确认后继续执行）

职责边界：
- 管理 thread_id 与 task_id 的映射
- 管理任务元数据（状态、时间戳）
- 调用 Graph 执行业务逻辑
- 不处理 HTTP 请求解析（由 Controller 层负责）
"""

import json
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from app.core.exceptions import GraphExecutionError, TaskNotFoundError
from app.core.logger import get_logger
from app.graph.creation.builder import get_creation_graph
from app.schemas.response import TaskResponse, TaskStatusResponse
from app.services.task_store import TaskStore

logger = get_logger(__name__)

# 节点中文标签映射（前端展示用）
NODE_LABELS = {
    "planner": "生成大纲",
    "outline_confirmation": "大纲确认",
    "writer": "撰写章节",
    "reducer": "合并润色",
}


class CreationService:
    """Creation 业务服务

    管理创作任务的完整生命周期：创建 → 中断 → 恢复 → 完成。

    Attributes:
        checkpointer: LangGraph Checkpointer 实例
        _graph: 编译后的 Creation Graph（惰性初始化）
        _tasks: 任务元数据存储
    """

    def __init__(self, checkpointer: BaseCheckpointSaver, task_store: TaskStore) -> None:
        """初始化 Creation Service

        Args:
            checkpointer: LangGraph Checkpointer 实例
            task_store: SQLite 任务持久化存储
        """
        self.checkpointer = checkpointer
        self.task_store = task_store
        self._graph = None
        self._tasks: dict[str, dict[str, Any]] = {}

    def _get_graph(self):
        """获取编译后的 Creation Graph（惰性初始化）"""
        if self._graph is None:
            self._graph = get_creation_graph(checkpointer=self.checkpointer)
        return self._graph

    def _generate_task_id(self) -> str:
        """生成唯一任务 ID"""
        return f"creation_{uuid4().hex[:12]}"

    def _save_task(
        self,
        task_id: str,
        thread_id: str,
        status: str,
        request_data: Optional[dict[str, Any]] = None,
    ) -> None:
        """保存任务元数据"""
        self._tasks[task_id] = {
            "task_id": task_id,
            "thread_id": thread_id,
            "graph_type": "creation",
            "status": status,
            "request": request_data,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

    def _update_task(self, task_id: str, **kwargs) -> None:
        """更新任务元数据"""
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id=task_id)
        self._tasks[task_id].update(kwargs)
        self._tasks[task_id]["updated_at"] = datetime.now()

    def _build_config(self, thread_id: str) -> dict:
        """构建 LangGraph 执行配置"""
        return {"configurable": {"thread_id": thread_id}}

    async def _persist_and_cleanup(
        self,
        task_id: str,
        thread_id: str,
        status: str,
        result: Optional[str] = None,
        outline_data: Optional[list] = None,
        error: Optional[str] = None,
    ) -> None:
        """将终态任务保存到 SQLite 并释放内存

        Args:
            task_id: 任务 ID
            thread_id: thread_id（等于 task_id）
            status: 终态（completed / failed）
            result: 最终结果文本
            outline_data: 大纲数据（用于持久化）
            error: 错误信息（failed 时）
        """
        task = self._tasks.get(task_id, {})
        request = task.get("request", {})

        # 保存到 SQLite
        logger.info(
            f"持久化创作任务 - task_id: {task_id}, status: {status}, "
            f"result_len: {len(result) if result else 0}, "
            f"outline_items: {len(outline_data) if outline_data else 0}, "
            f"topic: {request.get('topic')}, error: {error}"
        )
        try:
            save_data = {
                "task_id": task_id,
                "graph_type": "creation",
                "status": status,
                "topic": request.get("topic"),
                "description": request.get("description"),
                "result": result or "",
                "outline": json.dumps(outline_data, ensure_ascii=False) if outline_data else None,
                "error": error,
                "progress": 100.0 if status == "completed" else 0.0,
                "created_at": str(task.get("created_at", datetime.now())),
                "updated_at": str(datetime.now()),
            }
            logger.debug(f"保存数据: {save_data}")
            await self.task_store.save_task(save_data)
            logger.info(f"SQLite 保存成功 - task_id: {task_id}")
        except Exception as e:
            logger.error(f"保存任务到 SQLite 失败 - task_id: {task_id}, error: {e}", exc_info=True)

        # 从 _tasks dict 移除
        self._tasks.pop(task_id, None)

    # ============================================
    # 公开 API
    # ============================================

    async def start_task(
        self,
        topic: str,
        description: Optional[str] = None,
    ) -> TaskResponse:
        """创建并启动创作任务

        调用 Creation Graph，执行 PlannerNode 生成大纲后，
        在 outline_confirmation 中断点暂停，等待用户确认。

        Args:
            topic: 创作主题
            description: 创作描述（可选）

        Returns:
            TaskResponse: 包含 task_id 和初始状态

        Raises:
            GraphExecutionError: 图执行失败时抛出
        """
        task_id = self._generate_task_id()
        thread_id = task_id  # 使用 task_id 作为 thread_id

        self._save_task(
            task_id=task_id,
            thread_id=thread_id,
            status="running",
            request_data={"topic": topic, "description": description},
        )

        initial_state = {
            "topic": topic,
            "description": description,
            "outline": [],
            "sections": [],
            "final_draft": None,
            "messages": [],
            "current_node": None,
            "error": None,
        }

        config = self._build_config(thread_id)
        graph = self._get_graph()

        try:
            logger.info(f"创作任务启动 - task_id: {task_id}, topic: {topic}")

            result = await graph.ainvoke(initial_state, config)

            # 如果 ainvoke 正常返回（无中断），说明图已执行完成
            self._update_task(task_id, status="completed")
            logger.info(f"创作任务已完成 - task_id: {task_id}")

            return TaskResponse(
                task_id=task_id,
                status="completed",
                message="创作任务已完成",
                created_at=self._tasks[task_id]["created_at"],
            )

        except GraphInterrupt as e:
            # 图在 outline_confirmation 中断点暂停
            self._update_task(task_id, status="interrupted")
            logger.info(f"创作任务暂停（大纲待确认）- task_id: {task_id}")

            return TaskResponse(
                task_id=task_id,
                status="interrupted",
                message="大纲已生成，请确认后继续",
                created_at=self._tasks[task_id]["created_at"],
            )

        except Exception as e:
            self._update_task(task_id, status="failed", error=str(e))
            logger.error(f"创作任务失败 - task_id: {task_id}, error: {str(e)}")

            raise GraphExecutionError(
                message=f"创作任务执行失败: {str(e)}",
                details={"task_id": task_id, "topic": topic},
            ) from e

    async def resume_task(
        self,
        task_id: str,
        action: str,
        data: Optional[dict[str, Any]] = None,
    ) -> TaskResponse:
        """恢复被中断的创作任务

        在用户确认大纲后，继续执行后续流程（并发写作 → 合并）。

        Args:
            task_id: 任务 ID
            action: 恢复动作（confirm_outline / update_outline）
            data: 附加数据（update_outline 时包含新大纲）

        Returns:
            TaskResponse: 任务执行结果

        Raises:
            TaskNotFoundError: 任务不存在时抛出
            GraphExecutionError: 图执行失败时抛出
        """
        task = self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id=task_id)

        thread_id = task["thread_id"]
        config = self._build_config(thread_id)
        graph = self._get_graph()

        logger.info(f"恢复创作任务 - task_id: {task_id}, action: {action}")

        try:
            if action == "update_outline" and data and "outline" in data:
                # 先更新大纲，再恢复执行
                await graph.aupdate_state(config, {"outline": data["outline"]})

            result = await graph.ainvoke(Command(resume=True), config)

            # 正常返回表示图已完成
            self._update_task(task_id, status="completed")
            logger.info(f"创作任务恢复完成 - task_id: {task_id}")

            return TaskResponse(
                task_id=task_id,
                status="completed",
                message="创作任务已完成",
                created_at=task["created_at"],
            )

        except GraphInterrupt:
            # 可能出现二次中断（当前设计不会，但防御性处理）
            self._update_task(task_id, status="interrupted")
            logger.warning(f"创作任务再次中断 - task_id: {task_id}")

            return TaskResponse(
                task_id=task_id,
                status="interrupted",
                message="任务再次中断，请继续处理",
                created_at=task["created_at"],
            )

        except Exception as e:
            self._update_task(task_id, status="failed", error=str(e))
            logger.error(f"创作任务恢复失败 - task_id: {task_id}, error: {str(e)}")

            raise GraphExecutionError(
                message=f"创作任务恢复失败: {str(e)}",
                details={"task_id": task_id, "action": action},
            ) from e

    async def get_task_status(
        self,
        task_id: str,
        include_state: bool = False,
        include_history: bool = False,
    ) -> TaskStatusResponse:
        """查询创作任务状态

        Args:
            task_id: 任务 ID
            include_state: 是否包含完整图状态
            include_history: 是否包含执行历史

        Returns:
            TaskStatusResponse: 任务状态详情

        Raises:
            TaskNotFoundError: 任务不存在时抛出
        """
        task = self._tasks.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id=task_id)

        thread_id = task["thread_id"]
        config = self._build_config(thread_id)
        graph = self._get_graph()

        response = TaskStatusResponse(
            task_id=task_id,
            status=task["status"],
            current_node=None,
            awaiting=None,
            data=None,
            result=None,
            error=task.get("error"),
            progress=None,
            state=None,
            history=None,
            created_at=task["created_at"],
            updated_at=task["updated_at"],
        )

        try:
            # 获取当前图状态
            snapshot = await graph.aget_state(config)
            graph_state = snapshot.values if snapshot else {}

            # 提取当前节点信息
            current_node = graph_state.get("current_node")
            response.current_node = current_node

            # 计算进度
            response.progress = self._calculate_progress(graph_state, task["status"])

            # 提取结果
            if task["status"] == "completed":
                response.result = graph_state.get("final_draft")

            # 设置 awaiting 信息
            if task["status"] == "interrupted":
                response.awaiting = "outline_confirmation"

            # 附加完整状态
            if include_state:
                response.state = self._serialize_state(graph_state)

            # 附加执行历史
            if include_history:
                response.history = await self._get_history(config)

        except Exception as e:
            logger.warning(f"获取图状态失败 - task_id: {task_id}, error: {str(e)}")

        return response

    # ============================================
    # WebSocket 流式执行方法
    # ============================================

    async def start_task_streaming(
        self,
        topic: str,
        description: Optional[str],
        broadcaster: Any,
        client_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        """流式执行创作任务（WebSocket 推送进度）

        使用 LangGraph astream() 逐节点 yield 状态更新，在关键节点手动推送进度。
        """
        task_id = self._generate_task_id()
        thread_id = task_id

        self._save_task(
            task_id=task_id,
            thread_id=thread_id,
            status="running",
            request_data={"topic": topic, "description": description},
        )

        # 自动订阅
        broadcaster.subscribe(client_id, task_id)

        # 通知客户端任务已创建
        await broadcaster.send_to(
            client_id,
            {
                "type": "task_created",
                "requestId": request_id,
                "taskId": task_id,
                "status": "running",
                "createdAt": str(self._tasks[task_id]["created_at"]),
            },
        )

        initial_state = {
            "topic": topic,
            "description": description,
            "outline": [],
            "sections": [],
            "final_draft": None,
            "messages": [],
            "current_node": None,
            "error": None,
        }

        config = self._build_config(thread_id)
        graph = self._get_graph()

        try:
            logger.info(f"创作任务流式启动 - task_id: {task_id}, topic: {topic}")

            final_state: dict = {}
            total_sections = len(initial_state.get("outline", []))
            completed_writers = 0

            async for node_output in graph.astream(initial_state, config):
                # node_output: {"node_name": {节点输出的增量字典}}
                for node_name, partial in node_output.items():
                    if node_name == "__end__":
                        final_state = partial if isinstance(partial, dict) else {}
                        continue

                    if not isinstance(partial, dict):
                        continue

                    # 跟踪 writer 完成进度
                    if node_name == "writer" and "sections" in partial:
                        completed_writers += 1

                    current_node = partial.get("current_node", node_name)
                    label = NODE_LABELS.get(current_node, current_node)
                    progress = self._calculate_writer_progress(
                        current_node, completed_writers, total_sections,
                    )

                    await broadcaster.broadcast_update(
                        task_id,
                        {
                            "status": "running",
                            "currentNode": current_node,
                            "currentNodeLabel": label,
                            "progress": progress,
                        },
                    )

                    logger.debug(f"节点完成 - {node_name} ({label}), progress: {progress}")

            # astream() 遇到 interrupt_before 不会抛异常，而是停止 yield
            # 检查图状态是否有待处理的中断
            snapshot = await graph.aget_state(config)
            has_pending_interrupt = any(
                task.state is None for task in snapshot.tasks
            ) if snapshot and snapshot.tasks else False

            if has_pending_interrupt:
                # 图在中断点暂停（大纲待确认）
                self._update_task(task_id, status="interrupted")
                logger.info(f"创作任务流式暂停（大纲待确认）- task_id: {task_id}")

                graph_state = snapshot.values if snapshot else {}
                outline_data = None
                raw_outline = graph_state.get("outline")
                if raw_outline:
                    outline_data = [
                        {"title": item.get("title", ""), "summary": item.get("summary", "")}
                        for item in raw_outline
                    ]

                await broadcaster.broadcast_update(
                    task_id,
                    {
                        "status": "interrupted",
                        "currentNode": "outline_confirmation",
                        "currentNodeLabel": NODE_LABELS["outline_confirmation"],
                        "awaiting": "outline_confirmation",
                        "data": {"outline": outline_data} if outline_data else None,
                        "progress": self._calculate_progress(graph_state, "interrupted"),
                    },
                )
            else:
                # 正常完成
                self._update_task(task_id, status="completed")
                logger.info(f"创作任务流式完成 - task_id: {task_id}")

                # 从 checkpoint 读取最终状态（比 astream 的 final_state 更可靠）
                graph_state = snapshot.values if snapshot else {}

                result = graph_state.get("final_draft", "")
                created_at = self._tasks[task_id]["created_at"]

                # 提取大纲数据用于持久化
                outline_for_db = None
                raw_outline = graph_state.get("outline")
                if raw_outline:
                    outline_for_db = [
                        {"title": item.get("title", ""), "summary": item.get("summary", "")}
                        for item in raw_outline
                    ]

                # 持久化到 SQLite + 释放内存
                await self._persist_and_cleanup(
                    task_id, thread_id, "completed",
                    result=result or "", outline_data=outline_for_db,
                )

                await broadcaster.broadcast_result(task_id, result or "", created_at)

        except GraphInterrupt:
            self._update_task(task_id, status="interrupted")
            logger.info(f"创作任务流式暂停（大纲待确认）- task_id: {task_id}")

            # 获取大纲数据用于推送
            snapshot = await graph.aget_state(config)
            graph_state = snapshot.values if snapshot else {}
            outline_data = None
            raw_outline = graph_state.get("outline")
            if raw_outline:
                outline_data = [
                    {"title": item.get("title", ""), "summary": item.get("summary", "")}
                    for item in raw_outline
                ]

            await broadcaster.broadcast_update(
                task_id,
                {
                    "status": "interrupted",
                    "currentNode": "outline_confirmation",
                    "currentNodeLabel": NODE_LABELS["outline_confirmation"],
                    "awaiting": "outline_confirmation",
                    "data": {"outline": outline_data} if outline_data else None,
                    "progress": self._calculate_progress(graph_state, "interrupted"),
                },
            )

        except Exception as e:
            self._update_task(task_id, status="failed", error=str(e))
            logger.error(f"创作任务流式失败 - task_id: {task_id}, error: {e}")

            # 持久化到 SQLite + 释放内存
            await self._persist_and_cleanup(
                task_id, thread_id, "failed", error=str(e),
            )

            await broadcaster.broadcast_error(task_id, str(e))

    async def resume_task_streaming(
        self,
        task_id: str,
        action: str,
        data: Optional[dict[str, Any]],
        broadcaster: Any,
        client_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        """流式恢复被中断的创作任务（WebSocket 推送进度）"""
        task = self._tasks.get(task_id)
        if task is None:
            await broadcaster.send_to(
                client_id,
                {"type": "error", "requestId": request_id, "code": "TASK_NOT_FOUND", "message": f"任务不存在: {task_id}"},
            )
            return

        thread_id = task["thread_id"]
        config = self._build_config(thread_id)
        graph = self._get_graph()

        # 自动订阅
        broadcaster.subscribe(client_id, task_id)

        try:
            logger.info(f"恢复创作任务流式执行 - task_id: {task_id}, action: {action}")

            if action == "update_outline" and data and "outline" in data:
                await graph.aupdate_state(config, {"outline": data["outline"]})

            await broadcaster.broadcast_update(
                task_id,
                {
                    "status": "running",
                    "currentNode": "outline_confirmation",
                    "currentNodeLabel": NODE_LABELS["outline_confirmation"],
                    "progress": 30.0,
                },
            )

            # 获取大纲长度用于计算 writer 进度
            pre_snapshot = await graph.aget_state(config)
            pre_state = pre_snapshot.values if pre_snapshot else {}
            total_sections = len(pre_state.get("outline", []))

            final_state: dict = {}
            completed_writers = 0

            async for node_output in graph.astream(Command(resume=True), config):
                for node_name, partial in node_output.items():
                    if node_name == "__end__":
                        final_state = partial if isinstance(partial, dict) else {}
                        continue

                    if not isinstance(partial, dict):
                        continue

                    # 跟踪 writer 完成进度
                    if node_name == "writer" and "sections" in partial:
                        completed_writers += 1

                    current_node = partial.get("current_node", node_name)
                    label = NODE_LABELS.get(current_node, current_node)
                    progress = self._calculate_writer_progress(
                        current_node, completed_writers, total_sections,
                    )

                    await broadcaster.broadcast_update(
                        task_id,
                        {
                            "status": "running",
                            "currentNode": current_node,
                            "currentNodeLabel": label,
                            "progress": progress,
                        },
                    )

            # 检查是否有待处理的中断
            snapshot = await graph.aget_state(config)
            has_pending_interrupt = any(
                task.state is None for task in snapshot.tasks
            ) if snapshot and snapshot.tasks else False

            if has_pending_interrupt:
                self._update_task(task_id, status="interrupted")
                logger.info(f"创作任务恢复后再次中断 - task_id: {task_id}")
                await broadcaster.broadcast_update(
                    task_id,
                    {
                        "status": "interrupted",
                        "currentNode": "outline_confirmation",
                        "currentNodeLabel": NODE_LABELS["outline_confirmation"],
                        "awaiting": "outline_confirmation",
                    },
                )
            else:
                self._update_task(task_id, status="completed")
                logger.info(f"创作任务恢复流式完成 - task_id: {task_id}")

                # 从 checkpoint 读取最终状态（比 astream 的 final_state 更可靠）
                graph_state = snapshot.values if snapshot else {}

                result = graph_state.get("final_draft", "")
                created_at = task["created_at"]

                # 提取大纲数据用于持久化
                outline_for_db = None
                raw_outline = graph_state.get("outline")
                if raw_outline:
                    outline_for_db = [
                        {"title": item.get("title", ""), "summary": item.get("summary", "")}
                        for item in raw_outline
                    ]

                # 持久化到 SQLite + 释放内存
                await self._persist_and_cleanup(
                    task_id, thread_id, "completed",
                    result=result or "", outline_data=outline_for_db,
                )

                await broadcaster.broadcast_result(task_id, result or "", created_at)

        except GraphInterrupt:
            self._update_task(task_id, status="interrupted")
            logger.warning(f"创作任务再次中断 - task_id: {task_id}")
            await broadcaster.broadcast_update(
                task_id,
                {
                    "status": "interrupted",
                    "currentNode": "outline_confirmation",
                    "currentNodeLabel": NODE_LABELS["outline_confirmation"],
                    "awaiting": "outline_confirmation",
                },
            )

        except Exception as e:
            self._update_task(task_id, status="failed", error=str(e))
            logger.error(f"创作任务恢复流式失败 - task_id: {task_id}, error: {e}")

            # 持久化到 SQLite + 释放内存
            await self._persist_and_cleanup(
                task_id, thread_id, "failed", error=str(e),
            )

            await broadcaster.broadcast_error(task_id, str(e))

    # ============================================
    # 内部辅助方法
    # ============================================

    @staticmethod
    def _calculate_progress(state: dict, status: str) -> float:
        """计算任务进度百分比"""
        if status == "completed":
            return 100.0
        if status == "failed":
            return 0.0

        current_node = state.get("current_node", "")
        progress_map = {
            "planner": 20.0,
            "outline_confirmation": 30.0,
            "writer": 60.0,
            "reducer": 80.0,
        }
        return progress_map.get(current_node, 10.0)

    @staticmethod
    def _calculate_writer_progress(
        current_node: str, completed_writers: int, total_sections: int,
    ) -> float:
        """计算包含并发 writer 的总体进度

        进度分配：
        - planner: 10%
        - outline_confirmation: 20%
        - writer 阶段: 30% ~ 80%（按完成比例线性增长）
        - reducer: 80% ~ 95%
        - completed: 100%
        """
        if current_node == "planner":
            return 10.0
        if current_node == "outline_confirmation":
            return 20.0
        if current_node == "writer":
            if total_sections <= 0:
                return 55.0
            ratio = min(completed_writers / total_sections, 1.0)
            return 30.0 + ratio * 50.0  # 30% → 80%
        if current_node == "reducer":
            return 90.0
        return 10.0

    @staticmethod
    def _serialize_state(state: dict) -> dict:
        """序列化图状态为可传输格式"""
        serialized = {}
        for key, value in state.items():
            if key == "messages":
                serialized[key] = [
                    {"type": type(m).__name__, "content": getattr(m, "content", str(m))}
                    for m in (value or [])
                ]
            elif key == "outline":
                serialized[key] = [
                    {"title": item.get("title", ""), "summary": item.get("summary", "")}
                    for item in (value or [])
                ]
            elif key == "sections":
                serialized[key] = [
                    {"title": s.get("title", ""), "content": s.get("content", ""), "index": s.get("index", 0)}
                    for s in (value or [])
                ]
            else:
                serialized[key] = value
        return serialized

    async def _get_history(self, config: dict) -> list[dict]:
        """获取图执行历史（checkpoint 列表）"""
        history = []
        try:
            async for checkpoint in self.checkpointer.alist(config):
                history.append({
                    "checkpoint_id": getattr(checkpoint, "id", None),
                    "ts": getattr(checkpoint, "ts", None),
                })
        except Exception as e:
            logger.warning(f"获取执行历史失败: {str(e)}")
        return history
