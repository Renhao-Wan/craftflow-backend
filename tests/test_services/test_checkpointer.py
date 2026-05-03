"""Checkpointer 管理模块测试

测试 Checkpointer 的初始化、获取、关闭和重置逻辑。
使用 mock 隔离 PostgreSQL 连接和 Settings 配置。
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
        """测试初始化 MemorySaver（开发模式）"""
        with patch("app.services.checkpointer.settings") as mock_settings:
            mock_settings.use_persistent_checkpointer = False

            checkpointer = await init_checkpointer()

            assert checkpointer is not None
            assert isinstance(checkpointer, MemorySaver)

    @pytest.mark.asyncio
    async def test_init_returns_singleton(self):
        """测试重复初始化返回同一实例"""
        with patch("app.services.checkpointer.settings") as mock_settings:
            mock_settings.use_persistent_checkpointer = False

            cp1 = await init_checkpointer()
            cp2 = await init_checkpointer()

            assert cp1 is cp2

    @pytest.mark.asyncio
    async def test_init_postgres_saver(self):
        """测试初始化 PostgresSaver（生产模式）"""
        mock_saver = AsyncMock()

        with (
            patch("app.services.checkpointer.settings") as mock_settings,
            patch(
                "app.services.checkpointer._create_postgres_saver",
                new_callable=AsyncMock,
                return_value=mock_saver,
            ) as mock_create,
        ):
            mock_settings.use_persistent_checkpointer = True

            checkpointer = await init_checkpointer()

            assert checkpointer is mock_saver
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_failure_raises_checkpointer_error(self):
        """测试初始化失败时抛出 CheckpointerError"""
        with (
            patch("app.services.checkpointer.settings") as mock_settings,
            patch(
                "app.services.checkpointer._create_postgres_saver",
                new_callable=AsyncMock,
                side_effect=ConnectionError("连接失败"),
            ),
        ):
            mock_settings.use_persistent_checkpointer = True

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
            mock_settings.use_persistent_checkpointer = False

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
            mock_settings.use_persistent_checkpointer = False

            await init_checkpointer()
            await close_checkpointer()

            with pytest.raises(CheckpointerError):
                get_checkpointer()

    @pytest.mark.asyncio
    async def test_close_when_not_initialized(self):
        """测试未初始化时关闭不报错"""
        await close_checkpointer()  # 应该静默完成

    @pytest.mark.asyncio
    async def test_close_postgres_saver_closes_connection(self):
        """测试关闭 PostgresSaver 时关闭连接"""
        mock_conn = AsyncMock()
        mock_saver = MagicMock()
        mock_saver.conn = mock_conn

        with (
            patch("app.services.checkpointer.settings") as mock_settings,
            patch(
                "app.services.checkpointer._create_postgres_saver",
                new_callable=AsyncMock,
                return_value=mock_saver,
            ),
        ):
            mock_settings.use_persistent_checkpointer = True

            await init_checkpointer()
            await close_checkpointer()

            mock_conn.close.assert_called_once()


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
            mock_settings.use_persistent_checkpointer = False

            cp1 = await init_checkpointer()
            reset_checkpointer()
            cp2 = await init_checkpointer()

            assert cp1 is not cp2
