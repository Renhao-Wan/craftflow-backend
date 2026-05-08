"""Polishing 业务服务层

封装 Polishing Graph 的业务逻辑，包括：
- 任务创建（发起三档润色流程）
- 任务状态查询

职责边界：
- 管理 thread_id 与 task_id 的映射
- 管理任务元数据（状态、时间戳）
- 调用 Graph 执行业务逻辑
- 不处理 HTTP 请求解析（由 Controller 层负责）
"""

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from langgraph.checkpoint.base import BaseCheckpointSaver
from app.core.exceptions import GraphExecutionError, TaskNotFoundError
from app.core.logger import get_logger
from app.graph.polishing.builder import get_polishing_graph
from app.graph.polishing.nodes import register_progress_callback, unregister_progress_callback
from app.schemas.response import TaskResponse, TaskStatusResponse
from app.services.checkpointer import cleanup_checkpoint
from app.services.task_store import TaskStore

logger = get_logger(__name__)

# 润色模式名称映射
MODE_NAMES = {
    1: "极速格式化",
    2: "专家对抗审查",
    3: "事实核查",
}

# 节点中文标签映射（前端展示用）
NODE_LABELS = {
    "router": "路由决策",
    "formatter": "极速格式化",
    "debate": "专家对抗审查",
    "fact_checker": "事实核查",
}

# Debate 子图节点标签映射
DEBATE_NODE_LABELS = {
    "author": "作者重写",
    "editor": "编辑评审",
    "increment_iteration": "迭代更新",
    "finalize": "最终定稿",
}


class PolishingService:
    """Polishing 业务服务

    管理润色任务的生命周期。Polishing Graph 无 HITL 中断，
    任务创建后直接执行至完成。

    Attributes:
        checkpointer: LangGraph Checkpointer 实例
        _graph: 编译后的 Polishing Graph（惰性初始化）
        _tasks: 任务元数据存储
    """

    def __init__(self, checkpointer: BaseCheckpointSaver, task_store: TaskStore) -> None:
        """初始化 Polishing Service

        Args:
            checkpointer: LangGraph Checkpointer 实例
            task_store: SQLite 任务持久化存储
        """
        self.checkpointer = checkpointer
        self.task_store = task_store
        self._graph = None
        self._tasks: dict[str, dict[str, Any]] = {}

    def _get_graph(self):
        """获取编译后的 Polishing Graph（惰性初始化）"""
        if self._graph is None:
            self._graph = get_polishing_graph(checkpointer=self.checkpointer)
        return self._graph

    def _generate_task_id(self) -> str:
        """生成唯一任务 ID"""
        return f"polishing_{uuid4().hex[:12]}"

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
            "graph_type": "polishing",
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
        fact_check_result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """将终态任务保存到 SQLite 并释放内存"""
        task = self._tasks.get(task_id, {})
        request = task.get("request", {})
        content = request.get("content", "")
        mode = request.get("mode")

        logger.info(
            f"持久化润色任务 - task_id: {task_id}, status: {status}, "
            f"result_len: {len(result) if result else 0}, "
            f"mode: {mode}, error: {error}"
        )
        try:
            save_data = {
                "task_id": task_id,
                "graph_type": "polishing",
                "status": status,
                "topic": self._extract_topic(content) if content else None,
                "description": fact_check_result,  # 核查报告存入 description
                "content": content,
                "mode": mode,
                "result": result or "",
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

        # 清理 checkpoint 数据
        await cleanup_checkpoint(thread_id)

        self._tasks.pop(task_id, None)

    # ============================================
    # 公开 API
    # ============================================

    async def start_task(
        self,
        content: str,
        mode: int = 2,
    ) -> TaskResponse:
        """创建并执行润色任务

        调用 Polishing Graph 执行指定模式的润色流程。
        图执行完成后直接返回结果（无 HITL 中断）。

        Args:
            content: 待润色的 Markdown 内容
            mode: 润色模式（1=极速格式化, 2=专家对抗审查, 3=事实核查）

        Returns:
            TaskResponse: 包含 task_id 和执行状态

        Raises:
            GraphExecutionError: 图执行失败时抛出
        """
        task_id = self._generate_task_id()
        thread_id = task_id

        self._save_task(
            task_id=task_id,
            thread_id=thread_id,
            status="running",
            request_data={"content": content, "mode": mode},
        )

        initial_state = {
            "content": content,
            "mode": mode,
            "current_node": None,
            "error": None,
            "needs_revision": False,
            "formatted_content": None,
            "fact_check_result": None,
            "debate_history": [],
            "final_content": None,
            "scores": [],
            "overall_score": None,
            "messages": [],
            "task_id": task_id,
        }

        config = self._build_config(thread_id)
        graph = self._get_graph()

        mode_name = MODE_NAMES.get(mode, f"模式{mode}")
        logger.info(f"润色任务启动 - task_id: {task_id}, mode: {mode} ({mode_name})")

        try:
            result = await graph.ainvoke(initial_state, config)

            # 检查图执行是否产生错误
            error = result.get("error")
            if error:
                self._update_task(task_id, status="failed", error=error)
                logger.error(f"润色任务失败 - task_id: {task_id}, error: {error}")

                # 持久化 + 清理 + 释放内存
                await self._persist_and_cleanup(
                    task_id, thread_id, "failed", error=error,
                )

                raise GraphExecutionError(
                    message=f"润色任务执行失败: {error}",
                    details={"task_id": task_id, "mode": mode},
                )

            self._update_task(task_id, status="completed")
            created_at = self._tasks[task_id]["created_at"]

            # 从图状态提取结果
            graph_state = result or {}
            final_result = self._extract_result(graph_state) or ""
            fact_check_result = graph_state.get("fact_check_result")

            # 持久化 + 清理 + 释放内存
            await self._persist_and_cleanup(
                task_id, thread_id, "completed",
                result=final_result,
                fact_check_result=fact_check_result,
            )
            logger.info(f"润色任务完成 - task_id: {task_id}")

            return TaskResponse(
                task_id=task_id,
                status="completed",
                message=f"{mode_name}完成",
                created_at=created_at,
            )

        except GraphExecutionError:
            raise
        except Exception as e:
            self._update_task(task_id, status="failed", error=str(e))
            logger.error(f"润色任务异常 - task_id: {task_id}, error: {str(e)}")

            # 持久化 + 清理 + 释放内存
            await self._persist_and_cleanup(
                task_id, thread_id, "failed", error=str(e),
            )

            raise GraphExecutionError(
                message=f"润色任务执行异常: {str(e)}",
                details={"task_id": task_id, "mode": mode},
            ) from e

    async def get_task_status(
        self,
        task_id: str,
        include_state: bool = False,
        include_history: bool = False,
    ) -> TaskStatusResponse:
        """查询润色任务状态

        查询顺序：内存 _tasks（running/interrupted）→ TaskStore（completed/failed/interrupted）

        Args:
            task_id: 任务 ID
            include_state: 是否包含完整图状态
            include_history: 是否包含执行历史

        Returns:
            TaskStatusResponse: 任务状态详情

        Raises:
            TaskNotFoundError: 任务不存在时抛出
        """
        # 1. 先查内存（running / interrupted 任务）
        task = self._tasks.get(task_id)

        # 2. 内存未找到，查 TaskStore（仅查 polishing 类型）
        if task is None:
            row = await self.task_store.get_task(task_id, graph_type="polishing")
            if row is None:
                raise TaskNotFoundError(task_id=task_id)

            # 中断任务的 awaiting 字段（Polishing 无 HITL，但防御性处理）
            awaiting = None
            if row["status"] == "interrupted":
                awaiting = "outline_confirmation"

            # 构造 data 字段（前端对比视图需要 original_content）
            data = None
            if row.get("content") or row.get("mode"):
                data = {
                    "original_content": row.get("content", ""),
                    "mode": row.get("mode"),
                }

            return TaskStatusResponse(
                task_id=task_id,
                status=row["status"],
                current_node=None,
                current_node_label=None,
                awaiting=awaiting,
                data=data,
                result=row.get("result"),
                fact_check_result=row.get("description"),  # description 存储核查报告
                error=row.get("error"),
                progress=row.get("progress"),
                state=None,
                history=None,
                created_at=row.get("created_at"),
                updated_at=row.get("updated_at"),
            )

        # 3. 内存中找到（running / interrupted），从 checkpoint 读取图状态
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
            snapshot = await graph.aget_state(config)
            graph_state = snapshot.values if snapshot else {}

            current_node = graph_state.get("current_node")
            response.current_node = current_node
            response.current_node_label = (
                DEBATE_NODE_LABELS.get(current_node)
                or NODE_LABELS.get(current_node)
                or current_node
            )
            response.progress = self._calculate_progress(graph_state, task["status"])

            if task["status"] == "completed":
                response.result = self._extract_result(graph_state)
                response.fact_check_result = graph_state.get("fact_check_result")

            if include_state:
                response.state = self._serialize_state(graph_state)

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
        content: str,
        mode: int,
        broadcaster: Any,
        client_id: str,
        request_id: Optional[str] = None,
    ) -> None:
        """流式执行润色任务（WebSocket 推送进度）

        使用 astream_events 监听节点完成事件，在关键节点手动推送进度。
        Polishing Graph 无 HITL 中断，任务直接执行至完成。

        Args:
            content: 待润色的 Markdown 内容
            mode: 润色模式（1=极速格式化, 2=专家对抗审查, 3=事实核查）
            broadcaster: 任务广播服务
            client_id: 客户端 ID
            request_id: 请求 ID（可选，用于请求-响应配对）
        """
        task_id = self._generate_task_id()
        thread_id = task_id

        self._save_task(
            task_id=task_id,
            thread_id=thread_id,
            status="running",
            request_data={"content": content, "mode": mode},
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
            "content": content,
            "mode": mode,
            "current_node": None,
            "error": None,
            "needs_revision": False,
            "formatted_content": None,
            "fact_check_result": None,
            "debate_history": [],
            "final_content": None,
            "scores": [],
            "overall_score": None,
            "messages": [],
            "task_id": task_id,
        }

        config = self._build_config(thread_id)
        graph = self._get_graph()

        mode_name = MODE_NAMES.get(mode, f"模式{mode}")

        # 注册进度回调，让 fact_checker_node 能推送中间进度
        async def _progress_cb(node: str, label: str, progress: float) -> None:
            await broadcaster.broadcast_update(
                task_id,
                {
                    "status": "running",
                    "currentNode": node,
                    "currentNodeLabel": label,
                    "progress": progress,
                },
            )

        register_progress_callback(task_id, _progress_cb)

        try:
            logger.info(f"润色任务流式启动 - task_id: {task_id}, mode: {mode} ({mode_name})")

            # 使用 astream_events 监听所有层级的节点事件（包括子图）
            final_state: dict = {}
            async for event in graph.astream_events(initial_state, config, version="v2"):
                kind = event.get("event", "")
                data = event.get("data", {})
                node_name = event.get("name", "")

                # 只处理节点完成事件
                if kind == "on_chain_end" and isinstance(data, dict):
                    output = data.get("output")
                    if not isinstance(output, dict):
                        continue

                    # 跳过顶层图结束事件
                    if node_name == "LangGraph":
                        final_state = output
                        continue

                    # 获取节点标签和进度
                    current_node = output.get("current_node", node_name)
                    label = NODE_LABELS.get(current_node, current_node)

                    # 子图节点特殊处理
                    if current_node in ("author", "editor", "increment_iteration", "finalize"):
                        # debate 子图节点，计算更细粒度的进度
                        iteration = output.get("current_iteration", 0)
                        progress = self._calculate_debate_progress(current_node, iteration, mode)
                        label = DEBATE_NODE_LABELS.get(current_node, label)
                    elif current_node == "fact_checker":
                        progress = self._calculate_fact_checker_progress(output, mode)
                    else:
                        progress = self._calculate_progress(output, "running")

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

            # 正常返回 = 图已完成
            self._update_task(task_id, status="completed")
            logger.info(f"润色任务流式完成 - task_id: {task_id}")

            # 从 checkpoint 读取最终状态（比 astream 的 final_state 更可靠）
            snapshot = await graph.aget_state(config)
            graph_state = snapshot.values if snapshot else {}

            result = self._extract_result(graph_state)
            fact_check_result = graph_state.get("fact_check_result")
            created_at = self._tasks[task_id]["created_at"]

            # 持久化到 SQLite + 释放内存
            await self._persist_and_cleanup(
                task_id, thread_id, "completed",
                result=result or "",
                fact_check_result=fact_check_result,
            )

            await broadcaster.broadcast_result(
                task_id, result or "", created_at,
                fact_check_result=fact_check_result,
            )

        except Exception as e:
            self._update_task(task_id, status="failed", error=str(e))
            logger.error(f"润色任务流式失败 - task_id: {task_id}, error: {e}")

            # 持久化到 SQLite + 释放内存
            await self._persist_and_cleanup(
                task_id, thread_id, "failed", error=str(e),
            )

            await broadcaster.broadcast_error(task_id, str(e))
        finally:
            unregister_progress_callback(task_id)

    # ============================================
    # 内部辅助方法
    # ============================================

    @staticmethod
    def _extract_result(state: dict) -> Optional[str]:
        """从图状态中提取最终结果（文章内容）"""
        # Mode 2 (Debate) 和 Mode 3 (Fact Checker + Debate) 的结果在 final_content
        final_content = state.get("final_content")
        if final_content:
            return final_content

        # Mode 1 (Formatter) 的结果在 formatted_content
        formatted_content = state.get("formatted_content")
        if formatted_content:
            return formatted_content

        # Mode 3 没有进入修正流程时，返回原始内容（核查报告不作为文章结果）
        # 核查报告通过 fact_check_result 字段单独传递
        content = state.get("content")
        if content:
            return content

        return None

    @staticmethod
    def _extract_topic(content: str) -> str:
        """从 Markdown 内容提取主题（标题或前 15 字）

        优先取第一个 Markdown 标题（# 开头），否则取第一行非空前 15 字。
        """
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("# "):
                return stripped[2:].strip()[:100]
            # 非标题行，取前 15 字
            return stripped[:15] + "..." if len(stripped) > 15 else stripped
        return "润色任务"

    @staticmethod
    def _calculate_progress(state: dict, status: str) -> float:
        """计算任务进度百分比"""
        if status == "completed":
            return 100.0
        if status == "failed":
            return 0.0

        current_node = state.get("current_node", "")
        progress_map = {
            "router": 10.0,
            "formatter": 60.0,
            "debate": 60.0,
            "fact_checker": 30.0,
        }
        return progress_map.get(current_node, 10.0)

    @staticmethod
    def _calculate_debate_progress(
        node_name: str, iteration: int, mode: int,
    ) -> float:
        """计算 Debate 子图节点的进度

        进度分配：
        - mode 2: router(10%) → debate(10%-90%) → 完成(100%)
        - mode 3: router(10%) → fact_checker(10%-50%) → debate(50%-90%) → 完成(100%)

        Args:
            node_name: 子图节点名称
            iteration: 当前迭代轮次
            mode: 润色模式
        """
        max_iterations = 3  # 默认最大迭代次数

        # debate 在整体进度中的范围
        if mode == 3:
            debate_start = 50.0
            debate_end = 90.0
        else:
            debate_start = 10.0
            debate_end = 90.0

        debate_range = debate_end - debate_start
        iteration_progress = iteration / max_iterations

        # 每轮迭代的进度分配
        per_iteration = debate_range / max_iterations

        if node_name == "author":
            # author 完成 = 当前轮次开始 + 40% 的轮次进度
            return debate_start + (iteration_progress * debate_range) + per_iteration * 0.4
        elif node_name == "editor":
            # editor 完成 = 当前轮次开始 + 80% 的轮次进度
            return debate_start + (iteration_progress * debate_range) + per_iteration * 0.8
        elif node_name == "increment_iteration":
            # 迭代更新 = 当前轮次完成
            return debate_start + ((iteration + 1) / max_iterations) * debate_range
        elif node_name == "finalize":
            # 最终定稿 = debate 结束
            return debate_end
        else:
            return debate_start

    @staticmethod
    def _calculate_fact_checker_progress(state: dict, mode: int) -> float:
        """计算 FactChecker 节点的进度

        进度分配：
        - mode 3: router(10%) → fact_checker(10%-50%) → debate(50%-90%) → 完成(100%)

        Args:
            state: 节点输出状态
            mode: 润色模式
        """
        if mode != 3:
            return 60.0

        # 使用 needs_revision 判断是否需要进入 debate
        needs_revision = state.get("needs_revision", False)

        if not needs_revision:
            # high 准确性，fact_checker 完成即任务完成
            return 90.0
        else:
            # medium/low，fact_checker 完成后还要进入 debate
            return 50.0

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
            elif key == "debate_history":
                serialized[key] = [
                    {
                        "round_number": r.round_number,
                        "author_content": r.author_content[:200] + "..."
                        if len(r.author_content) > 200
                        else r.author_content,
                        "editor_feedback": r.editor_feedback,
                        "editor_score": r.editor_score,
                    }
                    for r in (value or [])
                ]
            elif key == "scores":
                serialized[key] = [
                    {
                        "dimension": s.dimension,
                        "score": s.score,
                        "comment": s.comment,
                    }
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
