"""Checkpointer 管理模块测试

测试 Checkpointer 的初始化、获取、关闭和重置逻辑。
使用 mock 隔离外部依赖和 Settings 配置。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langgraph.checkpoint.memory import MemorySaver

from app.core.exceptions import CheckpointerError
from app.services.checkpointer import (
    close_checkpointer,
    get_checkpointer,
    init_checkpointer,
    reset_checkpointer,
)


@pytest.fixture(autouse=True)
def _cleanup_checkpointer():
    """每个测试前后重置 Checkpointer 单例"""
    reset_checkpointer()
    yield
    reset_checkpointer()


# ============================================
# init_checkpointer 测试
# ============================================


class TestInitCheckpointer:
    """测试 Checkpointer 初始化"""

    @pytest.mark.asyncio
    async def test_init_memory_saver(self):
        """测试初始化 MemorySaver（memory 模式）"""
        with patch("app.services.checkpointer.settings") as mock_settings:
            mock_settings.checkpointer_backend = "memory"

            checkpointer = await init_checkpointer()

            assert checkpointer is not None
            assert isinstance(checkpointer, MemorySaver)

    @pytest.mark.asyncio
    async def test_init_returns_singleton(self):
        """测试重复初始化返回同一实例"""
        with patch("app.services.checkpointer.settings") as mock_settings:
            mock_settings.checkpointer_backend = "memory"

            cp1 = await init_checkpointer()
            cp2 = await init_checkpointer()

            assert cp1 is cp2

    @pytest.mark.asyncio
    async def test_init_sqlite_saver(self):
        """测试初始化 SqliteSaver（sqlite 模式）"""
        with patch("app.services.checkpointer.settings") as mock_settings:
            mock_settings.checkpointer_backend = "sqlite"

            checkpointer = await init_checkpointer()

            assert checkpointer is not None
            assert not isinstance(checkpointer, MemorySaver)

    @pytest.mark.asyncio
    async def test_init_postgres_saver(self):
        """测试初始化 PostgresSaver（postgres 模式）"""
        mock_saver = AsyncMock()
        mock_closer = AsyncMock()

        with (
            patch("app.services.checkpointer.settings") as mock_settings,
            patch.object(
                __import__(
                    "app.services.checkpointer", fromlist=["_FACTORIES"]
                )._FACTORIES["postgres"],
                "create",
                new_callable=AsyncMock,
                return_value=(mock_saver, mock_closer),
            ),
        ):
            mock_settings.checkpointer_backend = "postgres"

            checkpointer = await init_checkpointer()

            assert checkpointer is mock_saver

    @pytest.mark.asyncio
    async def test_init_invalid_backend_raises_error(self):
        """测试无效后端名称抛出错误"""
        with patch("app.services.checkpointer.settings") as mock_settings:
            mock_settings.checkpointer_backend = "invalid"

            with pytest.raises(CheckpointerError) as exc_info:
                await init_checkpointer()

            assert "未知的 Checkpointer 后端" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_init_failure_raises_checkpointer_error(self):
        """测试初始化失败时抛出 CheckpointerError"""
        with (
            patch("app.services.checkpointer.settings") as mock_settings,
            patch.object(
                __import__(
                    "app.services.checkpointer", fromlist=["_FACTORIES"]
                )._FACTORIES["postgres"],
                "create",
                new_callable=AsyncMock,
                side_effect=ConnectionError("连接失败"),
            ),
        ):
            mock_settings.checkpointer_backend = "postgres"

            with pytest.raises(CheckpointerError) as exc_info:
                await init_checkpointer()

            assert "初始化失败" in str(exc_info.value.message)


# ============================================
# get_checkpointer 测试
# ============================================


class TestGetCheckpointer:
    """测试 Checkpointer 获取"""

    def test_get_before_init_raises_error(self):
        """测试初始化前获取 Checkpointer 抛出错误"""
        with pytest.raises(CheckpointerError) as exc_info:
            get_checkpointer()

        assert "尚未初始化" in str(exc_info.value.message)

    @pytest.mark.asyncio
    async def test_get_after_init_returns_instance(self):
        """测试初始化后获取 Checkpointer 返回实例"""
        with patch("app.services.checkpointer.settings") as mock_settings:
            mock_settings.checkpointer_backend = "memory"

            initialized = await init_checkpointer()
            retrieved = get_checkpointer()

            assert retrieved is initialized


# ============================================
# close_checkpointer 测试
# ============================================


class TestCloseCheckpointer:
    """测试 Checkpointer 关闭"""

    @pytest.mark.asyncio
    async def test_close_resets_singleton(self):
        """测试关闭后单例被重置"""
        with patch("app.services.checkpointer.settings") as mock_settings:
            mock_settings.checkpointer_backend = "memory"

            await init_checkpointer()
            await close_checkpointer()

            with pytest.raises(CheckpointerError):
                get_checkpointer()

    @pytest.mark.asyncio
    async def test_close_when_not_initialized(self):
        """测试未初始化时关闭不报错"""
        await close_checkpointer()  # 应该静默完成

    @pytest.mark.asyncio
    async def test_close_sqlite_saver_closes_connection(self):
        """测试关闭 SqliteSaver 时关闭连接"""
        with patch("app.services.checkpointer.settings") as mock_settings:
            mock_settings.checkpointer_backend = "sqlite"

            await init_checkpointer()

            cp = get_checkpointer()
            conn = cp.conn

            await close_checkpointer()

            # 连接应已关闭（再次关闭会报错说明已关）
            with pytest.raises(Exception):
                await conn.execute("SELECT 1")


# ============================================
# reset_checkpointer 测试
# ============================================


class TestResetCheckpointer:
    """测试 Checkpointer 重置（测试辅助）"""

    def test_reset_clears_singleton(self):
        """测试重置清除单例"""
        reset_checkpointer()

        with pytest.raises(CheckpointerError):
            get_checkpointer()

    @pytest.mark.asyncio
    async def test_reset_allows_reinitialization(self):
        """测试重置后可以重新初始化"""
        with patch("app.services.checkpointer.settings") as mock_settings:
            mock_settings.checkpointer_backend = "memory"

            cp1 = await init_checkpointer()
            reset_checkpointer()
            cp2 = await init_checkpointer()

            assert cp1 is not cp2
